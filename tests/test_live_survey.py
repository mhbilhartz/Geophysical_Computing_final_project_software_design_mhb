"""Deterministic async scheduling plus actual production-backed UI calculations."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import csv
import io
import threading
import time
import unittest
from unittest.mock import patch

from bokeh.document import Document
import numpy as np

from tunnel_resistivity.live import LatestOnlyRunner
from tunnel_resistivity.survey import SurveyCancelled, forward_survey, generate_survey
from tunnel_resistivity.solver_2p5d import solve_source_pair
from tunnel_resistivity.survey_simulation import SurveyParameters, plan_simulation, run_survey_plan
from tunnel_resistivity.survey_app import SurveySimulatorApp


class ManualScheduler:
    """Only the test thread invokes UI callbacks; worker callbacks are queued."""
    doc=None
    def __init__(self):self.timers=[];self.callbacks=[];self.lock=threading.Lock()
    def later(self,ms,callback):
        token=[callback,False];self.timers.append(token);return token
    def cancel(self,token):token[1]=True
    def dispatch(self,callback):
        with self.lock:self.callbacks.append(callback)
    def advance(self):
        timers,self.timers=self.timers,[]
        for callback,cancelled in timers:
            if not cancelled:callback()
        self.drain()
    def drain(self):
        with self.lock:callbacks,self.callbacks=self.callbacks,[]
        for callback in callbacks:callback()
    def wait_for(self,condition,timeout=30):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            self.drain()
            if condition():return
            time.sleep(.01)
        raise AssertionError('Timed out waiting for background completion')


class RunnerTests(unittest.TestCase):
    def runner(self,work):
        self.scheduler=ManualScheduler();self.results=[];self.errors=[];self.progress=[]
        runner=LatestOnlyRunner(work,self.scheduler,on_result=self.results.append,on_error=self.errors.append,
                                on_progress=lambda a,b:self.progress.append((a,b)))
        self.addCleanup(runner.close);return runner

    def test_rapid_changes_coalesce_to_one_latest_snapshot(self):
        calls=[]
        def work(value,**kwargs):calls.append(value);return value
        runner=self.runner(work)
        for value in range(12):runner.request(value)
        self.scheduler.advance();self.scheduler.wait_for(lambda:len(self.results)==1)
        self.assertEqual(calls,[11]);self.assertEqual(self.results,[11])

    def test_running_old_result_never_publishes_and_only_latest_pending_starts(self):
        entered=threading.Event();release=threading.Event();calls=[]
        def work(value,*,cancelled,progress):
            calls.append(value)
            if value=='old':entered.set();release.wait(5)
            return value  # Deliberately ignore cancellation to test generation protection.
        runner=self.runner(work);runner.request('old');self.scheduler.advance()
        self.assertTrue(entered.wait(3))
        runner.request('middle');runner.request('latest');self.scheduler.advance()
        release.set();self.scheduler.wait_for(lambda:self.results==['latest'])
        self.assertEqual(calls,['old','latest']);self.assertFalse(self.errors)

    def test_invalid_edit_invalidates_running_result_and_stale_progress(self):
        entered=threading.Event();release=threading.Event()
        def work(value,*,cancelled,progress):
            entered.set();release.wait(5);progress(1,1);return value
        runner=self.runner(work);runner.request(1);self.scheduler.advance();self.assertTrue(entered.wait(3))
        runner.invalidate();release.set();self.scheduler.wait_for(lambda:not runner.busy)
        self.assertEqual(self.results,[]);self.assertEqual(self.progress,[])

    def test_old_failure_is_ignored_and_new_failure_is_reported(self):
        entered=threading.Event();release=threading.Event()
        def work(value,**kwargs):
            if value=='old':entered.set();release.wait(5)
            raise ValueError(value)
        runner=self.runner(work);runner.request('old');self.scheduler.advance();self.assertTrue(entered.wait(3))
        runner.request('new');self.scheduler.advance();release.set()
        self.scheduler.wait_for(lambda:len(self.errors)==1)
        self.assertEqual(str(self.errors[0]),'new')

    def test_close_signals_cancellation_and_drops_callbacks(self):
        entered=threading.Event();release=threading.Event();observed=[]
        def work(value,*,cancelled,progress):
            entered.set();release.wait(5);observed.append(cancelled());return value
        runner=self.runner(work);runner.request(1);self.scheduler.advance();self.assertTrue(entered.wait(3))
        runner.close();runner.request(2);release.set()
        end=time.monotonic()+3
        while not observed and time.monotonic()<end:time.sleep(.01)
        self.scheduler.drain();self.assertEqual(observed,[True]);self.assertEqual(self.results,[])


class SurveyCancellationTests(unittest.TestCase):
    def test_cancel_before_start_runs_no_source_solver(self):
        with patch('tunnel_resistivity.survey.solve_source_pair',wraps=solve_source_pair) as solve:
            with self.assertRaises(SurveyCancelled):
                forward_survey(np.full((10,20),.01),generate_survey('wenner'),cancelled=lambda:True)
        solve.assert_not_called()

    def test_progress_and_cancel_between_actual_source_solves(self):
        event=threading.Event();progress=[]
        def update(done,total):
            progress.append((done,total))
            if done==1:event.set()
        plan=generate_survey('dipole-dipole',electrode_count=7,line_start_x_m=35)
        with patch('tunnel_resistivity.survey.solve_source_pair',wraps=solve_source_pair) as solve:
            with self.assertRaises(SurveyCancelled):
                forward_survey(np.full((10,20),.01),plan,n_wavenumbers=8,
                                cancelled=event.is_set,progress=update)
        self.assertEqual(solve.call_count,1);self.assertEqual(progress,[(0,4),(1,4)])

    def test_successful_progress_covers_every_unique_source(self):
        updates=[];plan=generate_survey('wenner',electrode_count=4,levels=(1,))
        result=forward_survey(np.full((10,20),.01),plan,n_wavenumbers=8,
                              progress=lambda done,total:updates.append((done,total)))
        self.assertEqual(updates,[(0,1),(1,1)])
        self.assertAlmostEqual(result.measurements[0].apparent_resistivity_ohm_m,100)
        with self.assertRaises(ValueError):forward_survey(np.full((10,20),.01),plan,progress=1)


class LiveParameterTests(unittest.TestCase):
    def test_auto_and_manual_plans_preserve_all_physical_inputs(self):
        p=SurveyParameters(array_type='schlumberger',receiver_spacing_steps=2,depth_m=22,radius_m=6,
                           center_x_m=55,host_resistivity=200,tunnel_resistivity=20,current_a=.3)
        plan=plan_simulation(p)
        self.assertEqual(plan.tunnel.depth_m,22);self.assertEqual(plan.tunnel.radius_m,6)
        self.assertEqual(plan.survey.measurements[0].electrodes.current_a,.3)
        manual=plan_simulation(replace(p,grid_mode='Manual',x_min_m=-50,x_max_m=150,height_m=100,nx=160,nz=80))
        self.assertEqual(manual.grid.nx,160);self.assertEqual(manual.grid.x_min_m,-50)

    def test_invalid_model_plan_and_budget_inputs(self):
        for changes in ({'host_resistivity':0},{'tunnel_resistivity':float('inf')},{'depth_m':1},
                        {'max_level':0},{'grid_mode':'other'},
                        {'grid_mode':'Manual','nx':1000,'nz':1000},
                        {'grid_mode':'Manual','x_min_m':40}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):plan_simulation(replace(SurveyParameters(),**changes))

    def test_real_pipeline_recovers_homogeneous_for_all_arrays(self):
        for kind in ('wenner','schlumberger','dipole-dipole'):
            plan=plan_simulation(SurveyParameters(array_type=kind,electrode_count=4,max_level=1,tunnel_resistivity=100))
            result=run_survey_plan(plan)
            self.assertAlmostEqual(result.data.measurements[0].apparent_resistivity_ohm_m,100)
            self.assertEqual(result.plan,plan)


class LiveAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # One real production result is shared only as immutable test input for UI rendering tests.
        cls.real=run_survey_plan(plan_simulation(SurveyParameters(electrode_count=4,max_level=1,tunnel_resistivity=5)))

    def make_app(self,work=run_survey_plan):
        scheduler=ManualScheduler()
        app=SurveySimulatorApp(initial_run=False,scheduler=scheduler,work=work)
        self.addCleanup(app.close);return app,scheduler

    def test_sliders_presets_and_custom_are_authoritative(self):
        app,scheduler=self.make_app()
        app.material.value='Water-filled';app.tunnel.value=1e8
        self.assertEqual(app.parameters().tunnel_resistivity,5)
        self.assertEqual(app.tunnel.value,5)
        app.material.value='Custom';app.tunnel.value=1234
        self.assertFalse(app.tunnel.disabled);self.assertEqual(app.parameters().tunnel_resistivity,1234)
        app.material.value='Air-filled'
        self.assertTrue(app.tunnel.disabled);self.assertEqual(app.parameters().tunnel_resistivity,1e8)
        self.assertEqual(app.radius.__class__.__name__,'FloatSlider');self.assertEqual(app.depth.__class__.__name__,'FloatSlider')

    def test_dynamic_array_spacing_and_level_limits(self):
        app,scheduler=self.make_app()
        app.array_type.value='schlumberger';self.assertTrue(app.receiver_steps.visible)
        app.receiver_steps.value=3;self.assertEqual(app.parameters().receiver_spacing_steps,3)
        app.array_type.value='dipole-dipole';self.assertTrue(app.dipole_steps.visible)
        self.assertEqual(app.parameters().receiver_spacing_steps,1)
        app.electrode_count.value=4
        self.assertEqual(app.levels.value,1);self.assertTrue(app.levels.disabled)
        self.assertGreater(app.levels.end,app.levels.start)
        app.radius.value=10
        self.assertGreater(app.depth.value,10)

    def test_every_control_reaches_plan_and_grid_modes_toggle(self):
        app,scheduler=self.make_app()
        for widget,value,name in ((app.depth,25,'depth_m'),(app.radius,7,'radius_m'),(app.center_x,60,'center_x_m'),
                                  (app.host,300,'host_resistivity'),(app.pitch,6,'electrode_spacing_m'),
                                  (app.current,.2,'current_a'),(app.line_start,25,'line_start_x_m'),
                                  (app.resolution,.8,'max_cell_size_m'),(app.padding,2.5,'padding_factor')):
            widget.value=value
            self.assertEqual(getattr(app.parameters(),name),value)
        app.grid_mode.value='Manual';self.assertTrue(app.manual_controls.visible);self.assertFalse(app.resolution.visible)
        app.x_min.value=-50;app.x_max.value=180;app.height.value=90;app.nx.value=160;app.nz.value=80
        plan=plan_simulation(app.parameters())
        self.assertEqual((plan.grid.x_min_m,plan.grid.x_max_m,plan.grid.height_m,plan.grid.nx,plan.grid.nz),(-50,180,90,160,80))

    def test_actual_automatic_run_and_reset_without_run_button(self):
        app,scheduler=self.make_app()
        app.electrode_count.value=4;app.material.value='Water-filled'
        scheduler.advance();scheduler.wait_for(lambda:app.run_number==1)
        self.assertEqual(app.latest.plan.parameters.tunnel_resistivity,5)
        self.assertEqual(app.status.alert_type,'success');self.assertFalse(hasattr(app,'run_button'))
        self.assertEqual(len(app.latest.data.measurements),1)
        # Reset itself schedules one automatic request; no expensive default run is needed here.
        app.reset_button.clicks+=1
        self.assertEqual(app.parameters(),SurveyParameters())
        self.assertTrue(app.download.disabled)

    def test_invalid_values_retain_result_and_do_not_start_work(self):
        calls=[]
        def work(plan,**kwargs):calls.append(plan);return self.real
        app,scheduler=self.make_app(work)
        app._publish(self.real);first=app.latest
        app.material.value='Custom';app.tunnel.value=0
        scheduler.advance()
        self.assertEqual(calls,[]);self.assertIs(app.latest,first)
        self.assertEqual(app.status.alert_type,'danger');self.assertTrue(app.download.disabled)
        self.assertIn('invalid',app.preview.object)

    def test_completed_views_previous_csv_and_bokeh_document(self):
        app,scheduler=self.make_app()
        app._publish(self.real);app._publish(self.real)
        self.assertEqual(app.run_number,2);self.assertIs(app.previous,self.real)
        self.assertEqual(len(app.latest_view[1].object.axes),3)
        self.assertIn('ρa',app.latest_view[3].object)
        rows=list(csv.DictReader(io.StringIO(app._csv().getvalue().decode())))
        self.assertEqual(len(rows),1)
        self.assertAlmostEqual(float(rows[0]['apparent_resistivity_ohm_m']),self.real.data.measurements[0].apparent_resistivity_ohm_m)
        document=app.view.server_doc(Document())
        self.assertTrue(document.roots)

    def test_sessions_are_independent_and_cleanup_cancels_work(self):
        first,scheduler=self.make_app();second,other=self.make_app()
        first.material.value='Water-filled'
        self.assertEqual(second.material.value,'Air-filled');self.assertIsNone(second.latest)
        first.close();scheduler.advance()
        self.assertTrue(first.runner.closed);self.assertFalse(second.runner.closed)

    def test_csv_follows_selected_snapshot_and_stays_disabled_for_pending_inputs(self):
        app,scheduler=self.make_app()
        app._publish(self.real)
        homogeneous=run_survey_plan(plan_simulation(SurveyParameters(electrode_count=4,max_level=1,tunnel_resistivity=100)))
        app._publish(homogeneous)
        app.tabs.active=1
        row=next(csv.DictReader(io.StringIO(app._csv().getvalue().decode())))
        self.assertEqual(float(row['tunnel_resistivity_ohm_m']),5)
        self.assertEqual(app.download.filename,'survey_1_wenner.csv')
        app.tabs.active=0
        row=next(csv.DictReader(io.StringIO(app._csv().getvalue().decode())))
        self.assertAlmostEqual(float(row['apparent_resistivity_ohm_m']),100)
        self.assertEqual(float(row['tunnel_resistivity_ohm_m']),100)
        app.radius.value=6
        app.tabs.active=1
        self.assertTrue(app.download.disabled)


if __name__=='__main__':unittest.main()
