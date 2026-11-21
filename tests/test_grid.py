"""Domain geometry, allocation preflight and existing-solver integration."""
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

import numpy as np

from tunnel_resistivity.grid import GridSpec, TunnelGeometry, suggest_grid, prepare_survey_model
from tunnel_resistivity.survey import Survey, generate_survey, forward_survey
from tunnel_resistivity.receivers import measure_receivers
from tunnel_resistivity.solver_2p5d import solve_source_pair


def one_measurement(kind='wenner'):
    full=generate_survey(kind)
    # Keep the full physical line and the central maximum-spread measurement.
    selected=[entry for entry in full.measurements if entry.level==2]
    return Survey(full.electrode_positions_x_m,(selected[len(selected)//2],))


class GridPlanningTests(unittest.TestCase):
    def setUp(self):
        self.survey=generate_survey('wenner');self.tunnel=TunnelGeometry()

    def test_default_bounds_follow_array_spread(self):
        for kind,bounds,counts in (('wenner',(-30,130,80),(128,64)),
                                  ('schlumberger',(-20,120,70),(112,56)),
                                  ('dipole-dipole',(-10,110,60),(96,48))):
            with self.subTest(kind=kind):
                grid=suggest_grid(generate_survey(kind),self.tunnel)
                self.assertEqual((grid.x_min_m,grid.x_max_m,grid.height_m),bounds)
                self.assertEqual((grid.nx,grid.nz),counts)
                self.assertEqual((grid.dx_m,grid.dz_m),(1.25,1.25))

    def test_increasing_spacing_and_spread_grows_domain_preserving_resolution(self):
        first=suggest_grid(self.survey,self.tunnel)
        spaced=suggest_grid(generate_survey('wenner',electrode_spacing_m=10,line_start_x_m=10),self.tunnel)
        wider=suggest_grid(generate_survey('wenner',electrode_count=12,levels=(1,2,3)),self.tunnel)
        for grid in (spaced,wider):
            self.assertGreater(grid.width_m,first.width_m)
            self.assertGreater(grid.height_m,first.height_m)
            self.assertLessEqual(grid.dx_m,1.25)
            self.assertLessEqual(grid.dz_m,1.25)

    def test_unused_physical_line_extent_is_included(self):
        plan=generate_survey('wenner',electrode_count=17,line_start_x_m=10,levels=(1,))
        grid=suggest_grid(plan,self.tunnel)
        self.assertEqual((grid.x_min_m,grid.x_max_m),(-20,120))
        plan.validate_domain(grid.x_min_m,grid.x_max_m,boundary_padding_m=30)

    def test_tunnel_outside_line_and_deeper_target_expand_bounds(self):
        original=suggest_grid(self.survey,self.tunnel)
        right=suggest_grid(self.survey,replace(self.tunnel,center_x_m=150))
        left=suggest_grid(self.survey,replace(self.tunnel,center_x_m=-80))
        deep=suggest_grid(self.survey,replace(self.tunnel,depth_m=35))
        self.assertGreater(right.x_max_m,original.x_max_m)
        self.assertLess(left.x_min_m,original.x_min_m)
        self.assertGreater(deep.height_m,original.height_m)
        self.assertGreater(right.x_max_m,155)
        self.assertLess(left.x_min_m,-85)
        self.assertGreater(deep.height_m,40)

    def test_explicit_padding_overrides_automatic_padding(self):
        grid=suggest_grid(self.survey,self.tunnel,side_padding_m=12,bottom_padding_m=17)
        self.assertEqual((grid.x_min_m,grid.x_max_m,grid.height_m),(18,82,37))

    def test_cell_size_is_upper_bound_and_radius_and_spacing_are_resolved(self):
        tunnel=replace(self.tunnel,radius_m=2)
        grid=suggest_grid(self.survey,tunnel,max_cell_size_m=2.)
        self.assertLessEqual(max(grid.dx_m,grid.dz_m),.5)
        self.assertGreaterEqual(tunnel.radius_m/max(grid.dx_m,grid.dz_m),4)
        self.assertGreaterEqual(5/grid.dx_m,4)
        fine=suggest_grid(self.survey,self.tunnel,max_cell_size_m=.73)
        self.assertLessEqual(max(fine.dx_m,fine.dz_m),.73)
        self.assertGreater(fine.cell_count,suggest_grid(self.survey,self.tunnel).cell_count)

    def test_shallow_roof_refines_depth_independently_of_horizontal_spacing(self):
        tunnel=replace(self.tunnel,depth_m=5.25)
        grid=suggest_grid(self.survey,tunnel)
        self.assertEqual(grid.dx_m,1.25)
        self.assertLessEqual(grid.dz_m,tunnel.roof_depth_m/2)
        prepared=prepare_survey_model(self.survey,tunnel,grid)
        self.assertFalse(np.any(prepared.tunnel_mask[:2]))
        self.assertTrue(any('aspect ratio' in note for note in prepared.warnings))

    def test_budget_rejects_before_allocating_and_does_not_silently_coarsen(self):
        with (patch('tunnel_resistivity.grid.circular_tunnel') as geometry,
              patch('tunnel_resistivity.grid.cell_centers') as centers):
            with self.assertRaisesRegex(ValueError,'not silently coarsened'):
                suggest_grid(self.survey,self.tunnel,max_cell_size_m=.1,max_cells=10000)
            with self.assertRaisesRegex(ValueError,'budget'):
                prepare_survey_model(self.survey,self.tunnel,GridSpec(-30,130,80,128,64),max_cells=100)
        geometry.assert_not_called();centers.assert_not_called()

    def test_invalid_auto_parameters(self):
        for name,values in (('max_cell_size_m',(0,-1,np.nan,np.inf,True)),
                            ('padding_factor',(0,-1,np.inf)),('min_padding_m',(0,-1)),
                            ('side_padding_m',(0,-1)),('bottom_padding_m',(0,-1)),
                            ('cells_per_radius',(0,3)),('cells_per_electrode_spacing',(0,1)),
                            ('max_cells',(0,3,True,1000.))):
            for value in values:
                with self.subTest(name=name,value=value),self.assertRaises(ValueError):
                    suggest_grid(self.survey,self.tunnel,**{name:value})
        with self.assertRaises(ValueError):suggest_grid(None,self.tunnel)
        with self.assertRaises(ValueError):suggest_grid(self.survey,None)

    def test_invalid_grid_dimensions_and_tunnel_geometry(self):
        for args in ((0,0,10,10,10),(10,0,10,10,10),(0,10,0,10,10),
                     (0,10,10,1,10),(0,10,10,10,True),(0,np.inf,10,10,10),
                     (1e20,1e20+1e6,10,10**6,10)):
            with self.subTest(args=args),self.assertRaises(ValueError):GridSpec(*args)
        for kwargs in ({'depth_m':5},{'depth_m':0},{'radius_m':0},{'center_x_m':np.nan},
                       {'radius_m':np.inf},{'center_x_m':True},{'center_x_m':1e20,'radius_m':1e-6}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):TunnelGeometry(**kwargs)
        grid=GridSpec(-.1,.2,1,2,2)
        self.assertEqual(grid.cell_count,4)

    def test_geometry_configuration_is_immutable(self):
        grid=suggest_grid(self.survey,self.tunnel)
        with self.assertRaises(FrozenInstanceError):grid.nx=200
        with self.assertRaises(FrozenInstanceError):self.tunnel.depth_m=10


class PreparedModelTests(unittest.TestCase):
    def setUp(self):
        self.plan=one_measurement();self.tunnel=TunnelGeometry()

    def test_world_position_and_mask_are_preserved_in_a_shifted_domain(self):
        grid=GridSpec(-43,137,80,144,64)
        model=prepare_survey_model(self.plan,self.tunnel,grid)
        x,z=grid.cell_centers();xx,zz=np.meshgrid(x,z)
        independent=(xx-50)**2+(zz-15)**2<=25
        np.testing.assert_array_equal(model.tunnel_mask,independent)
        self.assertAlmostEqual(float(xx[model.tunnel_mask].mean()),50,delta=grid.dx_m/2)
        self.assertAlmostEqual(float(zz[model.tunnel_mask].mean()),15,delta=grid.dz_m/2)
        self.assertEqual(model.conductivity.shape,(grid.nz,grid.nx))
        self.assertTrue(np.all(model.conductivity>0))
        self.assertTrue(np.all(np.isfinite(model.conductivity)))

    def test_manual_dimensions_are_respected_and_coarse_circle_is_reported(self):
        grid=GridSpec(0,100,50,80,40)
        model=prepare_survey_model(self.plan,replace(self.tunnel,radius_m=2),grid)
        self.assertEqual(model.grid,grid)
        self.assertTrue(any('four cells per radius' in note for note in model.warnings))
        self.assertLess(model.diagnostics['cells_per_radius_x'],4)
        self.assertAlmostEqual(model.diagnostics['sampled_tunnel_area_m2'],
                               model.tunnel_mask.sum()*grid.dx_m*grid.dz_m)

    def test_shallow_manual_grid_reports_receiver_reconstruction_fallback(self):
        model=prepare_survey_model(self.plan,TunnelGeometry(depth_m=6.2),GridSpec(0,100,40,80,20))
        self.assertFalse(model.tunnel_mask[0].any())
        self.assertTrue(model.tunnel_mask[1].any())
        self.assertTrue(any('first-row reconstruction' in note for note in model.warnings))

    def test_invalid_manual_placement_surface_row_and_empty_circle(self):
        for grid in (GridSpec(35,100,50,52,40),GridSpec(0,55,50,44,40),
                     GridSpec(0,100,20,80,16),GridSpec(0,100,50,80,2)):
            with self.subTest(grid=grid),self.assertRaises(ValueError):
                prepare_survey_model(self.plan,self.tunnel,grid)
        with self.assertRaisesRegex(ValueError,'no cell centers'):
            prepare_survey_model(self.plan,TunnelGeometry(radius_m=.1),GridSpec(0,100,50,4,8))
        with self.assertRaises(ValueError):prepare_survey_model(self.plan,self.tunnel,None)

    def test_invalid_resistivity_and_nonfinite_reciprocals_rejected(self):
        grid=suggest_grid(self.plan,self.tunnel)
        for name in ('host_resistivity','tunnel_resistivity'):
            for value in (0,-1,np.nan,np.inf,True,'100',1e-320):
                with self.subTest(name=name,value=value),self.assertRaises(ValueError):
                    prepare_survey_model(self.plan,self.tunnel,grid,**{name:value})

    def test_translation_preserves_grid_counts_and_conductivity(self):
        grid=suggest_grid(self.plan,self.tunnel)
        model=prepare_survey_model(self.plan,self.tunnel,grid)
        full=generate_survey('wenner',line_start_x_m=-70)
        selected=next(entry for entry in full.measurements if entry.level==2 and entry.electrodes.center_x_m==-50)
        shifted=Survey(full.electrode_positions_x_m,(selected,))
        shifted_tunnel=replace(self.tunnel,center_x_m=-50)
        shifted_grid=suggest_grid(shifted,shifted_tunnel)
        self.assertEqual((shifted_grid.nx,shifted_grid.nz),(grid.nx,grid.nz))
        self.assertEqual(shifted_grid.x_min_m,grid.x_min_m-100)
        moved=prepare_survey_model(shifted,shifted_tunnel,shifted_grid)
        np.testing.assert_array_equal(moved.tunnel_mask,model.tunnel_mask)
        np.testing.assert_array_equal(moved.conductivity,model.conductivity)

    def test_homogeneous_recovery_with_all_automatically_sized_array_types(self):
        for kind in ('wenner','schlumberger','dipole-dipole'):
            plan=one_measurement(kind);grid=suggest_grid(plan,self.tunnel)
            prepared=prepare_survey_model(plan,self.tunnel,grid,host_resistivity=100,tunnel_resistivity=100)
            result=forward_survey(prepared.conductivity,plan,n_wavenumbers=8,**grid.solver_kwargs())
            with self.subTest(kind=kind):
                self.assertAlmostEqual(result.measurements[0].apparent_resistivity_ohm_m,100)
                self.assertEqual(result.width_m,grid.width_m)
                self.assertEqual(result.x_origin_m,grid.x_min_m)
                self.assertEqual(result.nx,grid.nx)

    def test_air_water_models_use_existing_solver_and_identical_grid_arguments(self):
        grid=suggest_grid(self.plan,self.tunnel)
        for rho in (1e8,5.):
            prepared=prepare_survey_model(self.plan,self.tunnel,grid,tunnel_resistivity=rho)
            batch=forward_survey(prepared.conductivity,self.plan,n_wavenumbers=48,**grid.solver_kwargs())
            direct=measure_receivers(solve_source_pair(prepared.conductivity,self.plan.measurements[0].electrodes,
                                                       n_wavenumbers=48,**grid.solver_kwargs()))
            self.assertAlmostEqual(batch.measurements[0].voltage_v,direct.voltage_v,places=11)
            self.assertLess(batch.max_relative_mode_residual,1e-9)
            self.assertLess(batch.max_relative_mode_balance_error,1e-9)
            if rho>100:self.assertGreater(direct.apparent_resistivity_ohm_m,100)
            else:self.assertLess(direct.apparent_resistivity_ohm_m,100)


if __name__=='__main__':unittest.main()
