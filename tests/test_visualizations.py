"""Real field selection, plot data/units, receiver reuse and live snapshot guards."""
from dataclasses import replace
import threading
import unittest
from unittest.mock import patch

from bokeh.document import Document
import numpy as np
from matplotlib.colors import LogNorm,SymLogNorm
from matplotlib.quiver import Quiver

from tunnel_resistivity.fields import (FieldRequest,FieldResult,SourceFieldCache,default_measurement_index,solve_field_request)
from tunnel_resistivity.solver_2p5d import solve_source_pair
from tunnel_resistivity.survey import SurveyCancelled
from tunnel_resistivity.survey_simulation import SurveyParameters,plan_simulation,run_survey_plan
from tunnel_resistivity.survey_plotting import build_field_figure,build_surface_figure,build_survey_map
from tunnel_resistivity.survey_app import SurveySimulatorApp
from test_live_survey import ManualScheduler


class VisualizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.water=run_survey_plan(plan_simulation(SurveyParameters(array_type='dipole-dipole',electrode_count=7,tunnel_resistivity=5)))
        cls.homogeneous=run_survey_plan(plan_simulation(SurveyParameters(electrode_count=4,max_level=1,tunnel_resistivity=100)))
        cls.air=run_survey_plan(plan_simulation(SurveyParameters(electrode_count=4,max_level=1,tunnel_resistivity=1e8)))
        cls.water_field=solve_field_request(FieldRequest(cls.water,0))
        cls.homogeneous_field=solve_field_request(FieldRequest(cls.homogeneous,0))
        cls.air_field=solve_field_request(FieldRequest(cls.air,0))

    def test_field_request_validation_and_default_widest_nearest_measurement(self):
        for bad in (-1,True,1.,999):
            with self.subTest(index=bad),self.assertRaises(ValueError):FieldRequest(self.water,bad)
        with self.assertRaises(ValueError):FieldRequest(None,0)
        index=default_measurement_index(self.water)
        selected=self.water.plan.survey.measurements[index]
        self.assertEqual(selected.level,2)
        candidates=[m for m in self.water.plan.survey.measurements if m.level==2]
        self.assertEqual(abs(selected.electrodes.center_x_m-50),min(abs(m.electrodes.center_x_m-50) for m in candidates))

    def test_selected_fields_match_completed_receiver_data_and_exact_settings(self):
        for field in (self.water_field,self.homogeneous_field,self.air_field):
            request=field.request;data=request.result.data;s=field.solution
            stored=data.measurements[request.measurement_index]
            self.assertAlmostEqual(field.measurement.voltage_v,stored.voltage_v,places=11)
            self.assertAlmostEqual(field.measurement.apparent_resistivity_ohm_m,stored.apparent_resistivity_ohm_m,places=10)
            self.assertEqual(s.potential.shape,(data.nz,data.nx))
            self.assertTrue(np.all(s.conductivity>0) and np.all(np.isfinite(s.conductivity)))
            self.assertEqual(len(s.wavenumbers_per_m),data.n_wavenumbers)
            self.assertLess(s.max_relative_mode_residual,1e-9)

    def test_service_delegates_to_existing_solver_with_saved_cutoffs(self):
        request=FieldRequest(self.water,1)
        with patch('tunnel_resistivity.fields.solve_source_pair',wraps=solve_source_pair) as solver:
            field=solve_field_request(request)
        self.assertEqual(solver.call_count,1)
        kwargs=solver.call_args.kwargs
        self.assertEqual(kwargs['k_min'],self.water.data.k_min_per_m)
        self.assertEqual(kwargs['k_max'],self.water.data.k_max_per_m)
        self.assertEqual(kwargs['x_origin_m'],self.water.plan.grid.x_min_m)
        self.assertEqual(field.request,request)

    def test_field_request_cooperative_cancellation_before_and_after_solve(self):
        request=FieldRequest(self.water,0)
        with patch('tunnel_resistivity.fields.solve_source_pair',wraps=solve_source_pair) as solver:
            with self.assertRaises(SurveyCancelled):solve_field_request(request,cancelled=lambda:True)
        solver.assert_not_called()
        event=threading.Event()
        def source(*args,**kwargs):event.set();return self.water_field.solution
        with patch('tunnel_resistivity.fields.solve_source_pair',side_effect=source):
            with self.assertRaises(SurveyCancelled):solve_field_request(request,cancelled=event.is_set)

    def test_cache_reuses_source_but_relabels_changed_receivers(self):
        cache=SourceFieldCache();cache.put(self.water_field)
        entries=self.water.plan.survey.measurements
        source=self.water_field.request.electrodes
        index=next(i for i,m in enumerate(entries) if i!=0 and m.electrodes.a_x_m==source.a_x_m
                   and m.electrodes.b_x_m==source.b_x_m)
        field=cache.get(FieldRequest(self.water,index))
        self.assertIs(field.solution,self.water_field.solution)
        self.assertNotEqual(field.request.electrodes.m_x_m,source.m_x_m)
        self.assertAlmostEqual(field.measurement.voltage_v,self.water.data.measurements[index].voltage_v,places=11)
        surface=build_surface_figure(field)
        receiver_x=surface.axes[0].collections[0].get_offsets()[:,0]
        np.testing.assert_allclose(receiver_x,[field.request.electrodes.m_x_m,field.request.electrodes.n_x_m])

    def test_cache_is_bounded_and_never_reuses_a_different_snapshot(self):
        cache=SourceFieldCache(capacity=1);cache.put(self.water_field)
        self.assertIsNone(cache.get(FieldRequest(self.homogeneous,0)))
        cache.put(self.air_field);self.assertEqual(len(cache),1)
        self.assertIsNone(cache.get(FieldRequest(self.water,0)))
        cache.retain((self.water,));self.assertEqual(len(cache),0)

    def test_four_maps_have_correct_physical_data_extents_and_units(self):
        field=self.water_field;figure=build_field_figure(field);s=field.solution;g=field.request.result.plan.grid
        maps=[ax for ax in figure.axes if ax.images]
        self.assertEqual(len(maps),4);self.assertEqual(len(figure.axes),8)
        np.testing.assert_allclose(maps[0].images[0].get_array(),1/s.conductivity)
        np.testing.assert_array_equal(maps[1].images[0].get_array(),s.potential)
        np.testing.assert_array_equal(maps[3].images[0].get_array(),s.secondary_potential)
        for ax in maps:
            self.assertEqual(tuple(ax.images[0].get_extent()),(g.x_min_m,g.x_max_m,g.height_m,0))
            self.assertGreater(ax.get_ylim()[0],ax.get_ylim()[1])
            self.assertEqual(ax.patches[0].center,(50.,15.))
            self.assertEqual([text.get_text() for text in ax.texts],['A','B','M','N'])
        self.assertIsInstance(maps[1].images[0].norm,SymLogNorm)
        self.assertIn('A/m²',maps[2].get_title())
        self.assertTrue(any('Ω·m' in ax.get_ylabel() for ax in figure.axes))

    def test_current_direction_arrows_follow_actual_current_on_downward_depth_axis(self):
        field=self.water_field;s=field.solution;fig=build_field_figure(field)
        ax=[a for a in fig.axes if a.images][2]
        quiver=next(item for item in ax.collections if isinstance(item,Quiver))
        iz=slice(None,None,max(1,len(s.z)//15));ix=slice(None,None,max(1,len(s.x)//22))
        x=s.jx[iz,ix].ravel();z=s.jz[iz,ix].ravel();mag=np.hypot(x,z)
        keep=mag>max(float(np.hypot(s.jx,s.jz).max())*1e-12,1e-300)
        np.testing.assert_allclose(quiver.U[keep],x[keep]/mag[keep])
        np.testing.assert_allclose(quiver.V[keep],z[keep]/mag[keep])
        self.assertEqual(quiver.angles,'xy');self.assertGreater(ax.get_ylim()[0],ax.get_ylim()[1])

    def test_surface_receiver_differences_use_same_reconstruction(self):
        field=self.water_field;fig=build_surface_figure(field);ax=fig.axes[0]
        receivers=ax.collections[0].get_offsets()
        self.assertAlmostEqual(receivers[0,1]-receivers[1,1],field.measurement.secondary_voltage_v,places=12)
        self.assertEqual(ax.get_ylabel(),'Surface ΔV (V)')
        self.assertTrue(np.all(np.isfinite(ax.lines[0].get_ydata())))

    def test_survey_maps_are_actual_uninterpolated_midpoint_level_data(self):
        figure=build_survey_map(self.water,2)
        plots=[ax for ax in figure.axes if ax.get_xlabel().startswith('Full electrode')]
        rows=self.water.data.records()
        expected=np.array([[r['spread_center_x_m'],r['level']] for r in rows])
        for ax in plots:
            np.testing.assert_allclose(ax.collections[0].get_offsets(),expected)
            self.assertEqual(len(ax.collections[1].get_offsets()),1)
            self.assertIn('not depth',ax.get_ylabel())
            self.assertGreater(ax.get_ylim()[0],ax.get_ylim()[1])
        np.testing.assert_allclose(plots[0].collections[0].get_array(),[r['apparent_resistivity_ohm_m'] for r in rows])

    def test_homogeneous_plots_do_not_amplify_roundoff_or_invent_anomalies(self):
        fig=build_field_figure(self.homogeneous_field);plots=[ax for ax in fig.axes if ax.images]
        np.testing.assert_array_equal(plots[-1].images[0].get_array(),0)
        self.assertEqual(plots[-1].images[0].norm.vmax,1e-12)
        figure=build_survey_map(self.homogeneous,0)
        plots=[ax for ax in figure.axes if ax.get_xlabel().startswith('Full electrode')]
        np.testing.assert_allclose(plots[1].collections[0].get_array(),0,atol=0)
        self.assertEqual(plots[1].collections[0].norm.vmax,1e-6)
        self.assertGreater(plots[0].collections[0].norm.vmax/plots[0].collections[0].norm.vmin,1.1)

    def test_signed_nonpositive_apparent_data_are_not_clipped(self):
        datum=self.homogeneous.data.measurements[0]
        artificial=replace(datum,secondary_voltage_v=-2*datum.primary_voltage_v)
        result=replace(self.homogeneous,data=replace(self.homogeneous.data,measurements=(artificial,)))
        fig=build_survey_map(result)
        plot=next(ax for ax in fig.axes if ax.get_title()=='Apparent resistivity (Ω·m)')
        self.assertLess(plot.collections[0].get_array()[0],0)
        self.assertIsInstance(plot.collections[0].norm,SymLogNorm)

    def app(self):
        scheduler=ManualScheduler();app=SurveySimulatorApp(initial_run=False,scheduler=scheduler)
        self.addCleanup(app.close);return app,scheduler

    def test_live_field_selection_runs_no_extra_survey_and_reuses_shared_sources(self):
        app,scheduler=self.app();app._publish(self.water)
        app.measurement.value=0
        with patch.object(app.runner,'work',wraps=app.runner.work) as full:
            scheduler.advance();scheduler.wait_for(lambda:app.field_latest is not None)
            field=app.field_latest
            same=next(i for i,m in enumerate(self.water.plan.survey.measurements) if i!=0 and
                      m.electrodes.a_x_m==field.request.electrodes.a_x_m and m.electrodes.b_x_m==field.request.electrodes.b_x_m)
            with patch.object(app.field_runner,'work',wraps=app.field_runner.work) as selected:
                app.measurement.value=same;scheduler.advance()
                self.assertEqual(app.field_latest.request.measurement_index,same)
                selected.assert_not_called()
            full.assert_not_called()
        self.assertEqual(len(app._field_cache),1)

    def test_input_edits_invalidate_fields_and_prevent_stale_publication(self):
        app,scheduler=self.app();app._publish(self.water)
        app.measurement.value=0;app._publish_fields(self.water_field)
        self.assertIsNotNone(app.field_latest)
        app.radius.value=6
        app._publish_fields(self.water_field)
        self.assertIsNone(app.field_latest);self.assertTrue(app.field_download.disabled)
        self.assertIsNone(app._field_figure)
        self.assertIn('Controls changed',app.field_view[0].object)

    def test_a_late_field_for_another_measurement_cannot_replace_current_selection(self):
        app,scheduler=self.app();app._publish(self.water)
        app.measurement.value=1
        app._publish_fields(self.water_field)
        self.assertIsNone(app.field_latest)
        self.assertTrue(app.field_download.disabled)

    def test_previous_latest_tabs_field_snapshot_and_png_are_consistent(self):
        app,scheduler=self.app();app._publish(self.water);app._publish(self.homogeneous)
        app.tabs.active=1;app.measurement.value=0
        app._publish_fields(self.homogeneous_field)
        self.assertIsNone(app.field_latest)
        app._publish_fields(self.water_field)
        self.assertIs(app.field_latest.request.result,self.water)
        self.assertEqual(app.field_download.filename,'fields_survey_1_measurement_1.png')
        self.assertTrue(app._field_png().getvalue().startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertEqual(len(app.field_view[0].object.axes),8)
        self.assertEqual(len(app.explorer_tabs),3)
        self.assertTrue(app.view.server_doc(Document()).roots)

    def test_closing_app_cancels_field_runner_and_clears_cache(self):
        app,scheduler=self.app();app._publish(self.water);app.measurement.value=0
        app._publish_fields(self.water_field)
        app.close()
        self.assertTrue(app.runner.closed and app.field_runner.closed)
        self.assertEqual(len(app._field_cache),0)


if __name__=='__main__':unittest.main()
