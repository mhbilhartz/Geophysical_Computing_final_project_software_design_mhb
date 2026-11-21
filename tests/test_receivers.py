"""Signed ERT factors, surface reconstruction, and nonzero 2.5D receiver data."""
from dataclasses import replace
import unittest

import numpy as np

from tunnel_resistivity.electrodes import wenner, schlumberger, dipole_dipole
from tunnel_resistivity.geometry import circular_tunnel
from tunnel_resistivity.receivers import geometric_factor, sample_surface_potential, measure_receivers
from tunnel_resistivity.solver import solve_homogeneous
from tunnel_resistivity.solver_2p5d import solve_source_pair


def arrays(center=50., current=1.):
    return (wenner(center_x_m=center,spacing_m=10,current_a=current),
            schlumberger(center_x_m=center,ab_half_spacing_m=20,mn_half_spacing_m=2,current_a=current),
            dipole_dipole(center_x_m=center,spacing_m=5,separation_n=2,current_a=current))


class GeometricFactorTests(unittest.TestCase):
    def test_factors_match_independent_array_specific_formulas(self):
        for spacing in (1.,3.25,10.):
            for n in (1,2,5,20):
                w=wenner(center_x_m=0,spacing_m=spacing)
                s=schlumberger(center_x_m=0,ab_half_spacing_m=4*spacing,mn_half_spacing_m=spacing)
                d=dipole_dipole(center_x_m=0,spacing_m=spacing,separation_n=n)
                for array,expected in ((w,2*np.pi*spacing),
                                       (s,np.pi*((4*spacing)**2-spacing**2)/(2*spacing)),
                                       (d,-np.pi*spacing*n*(n+1)*(n+2))):
                    with self.subTest(array=array.array_type,a=spacing,n=n):
                        self.assertAlmostEqual(geometric_factor(array)/expected,1,delta=1e-12)

    def test_translation_and_current_do_not_change_geometric_factor(self):
        for original,shifted in zip(arrays(50,1),arrays(-150,.1)):
            self.assertAlmostEqual(geometric_factor(original),geometric_factor(shifted))

    def test_geometric_factor_scales_with_all_distances(self):
        for original,scaled in zip(arrays(50),
                                  (wenner(center_x_m=100,spacing_m=20),
                                   schlumberger(center_x_m=100,ab_half_spacing_m=40,mn_half_spacing_m=4),
                                   dipole_dipole(center_x_m=100,spacing_m=10,separation_n=2))):
            self.assertAlmostEqual(geometric_factor(scaled),2*geometric_factor(original))

    def test_wrong_type_or_numerically_unresolved_factor_rejected(self):
        for bad in (None,{},'wenner'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):geometric_factor(bad)
        distant=dipole_dipole(center_x_m=0,spacing_m=1,separation_n=10**8)
        with self.assertRaisesRegex(ValueError,'degenerate'):geometric_factor(distant)


class SurfaceReceiverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.solution=solve_source_pair(np.full((10,20),.01),arrays()[0],n_wavenumbers=8)

    def test_analytical_primary_at_surface_instead_of_top_cell(self):
        s=self.solution
        positions=np.array([.1,20.123,45.31,52.4,80.6,99.9])
        expected=100/(2*np.pi)*(1/abs(positions-s.electrodes.a_x_m)-1/abs(positions-s.electrodes.b_x_m))
        np.testing.assert_allclose(sample_surface_potential(s,positions),expected,rtol=1e-14)
        value=sample_surface_potential(s,45.31)
        self.assertIsInstance(value,float)
        self.assertAlmostEqual(value,expected[2])

    def test_even_quadratic_surface_reconstruction_and_off_grid_interpolation(self):
        s=self.solution
        # Smooth manufactured correction: linear in x, quadratic/even in z.
        xx,zz=np.meshgrid(s.x,s.z)
        secondary=.03*xx+2.+.01*zz**2
        fake=replace(s,secondary_potential=secondary)
        positions=np.array([21.3,42.8,55.0,77.7])
        actual=sample_surface_potential(fake,positions)-sample_surface_potential(s,positions)
        np.testing.assert_allclose(actual,.03*positions+2.,atol=1e-14)
        # This catches either constant first-row sampling or interpolating total V.

    def test_zero_secondary_wall_values_support_half_cell_edge_strips(self):
        s=self.solution
        fake=replace(s,secondary_potential=np.full_like(s.secondary_potential,2.))
        positions=np.array([s.dx/4,100-s.dx/4])
        correction=sample_surface_potential(fake,positions)-sample_surface_potential(s,positions)
        np.testing.assert_allclose(correction,1,atol=1e-14)

    def test_shallow_contrast_does_not_extrapolate_across_material_interface(self):
        s=self.solution
        sigma=s.conductivity.copy();sigma[1,:]=.001
        secondary=np.full_like(s.secondary_potential,2.)
        secondary[1,:]=100.  # Deliberately sharp change below the host top cell.
        fake=replace(s,conductivity=sigma,secondary_potential=secondary)
        correction=sample_surface_potential(fake,[45.,55.])-sample_surface_potential(s,[45.,55.])
        np.testing.assert_allclose(correction,2.)

    def test_invalid_receiver_coordinates_rejected_without_silent_clamping(self):
        s=self.solution
        for bad in (0.,100.,-.1,101.,s.electrodes.a_x_m,s.electrodes.b_x_m,
                    np.nan,np.inf,[],[[20.]],1+1j,True,'50',None,['bad']):
            with self.subTest(x=bad),self.assertRaises(ValueError):
                sample_surface_potential(s,bad)

    def test_wrong_solver_and_corrupt_surface_grid_rejected(self):
        old=solve_homogeneous(nx=4,nz=2)
        with self.assertRaisesRegex(ValueError,'Solution25D'):sample_surface_potential(old,50)
        with self.assertRaisesRegex(ValueError,'Solution25D'):measure_receivers(old)
        for fake in (replace(self.solution,secondary_potential=np.full((10,20),np.nan)),
                     replace(self.solution,z=self.solution.z+1),
                     replace(self.solution,dx=-1)):
            with self.assertRaises(ValueError):sample_surface_potential(fake,50)


class ReceiverPhysicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.configurations=arrays()
        cls.models={}
        for name,rho in (('air',1e8),('water',5.)):
            sigma,_=circular_tunnel(nx=80,nz=40,host_resistivity=100,tunnel_resistivity=rho)
            for array in cls.configurations:
                cls.models[name,array.array_type]=solve_source_pair(sigma,array)

    def test_homogeneous_resistivity_recovery_multiple_grids_and_arrays(self):
        for rho in (5.,100.,2500.):
            for nz,nx in ((8,16),(20,40)):
                for array in self.configurations:
                    with self.subTest(rho=rho,grid=(nx,nz),array=array.array_type):
                        solution=solve_source_pair(np.full((nz,nx),1/rho),array,n_wavenumbers=8)
                        datum=measure_receivers(solution)
                        self.assertAlmostEqual(datum.apparent_resistivity_ohm_m/rho,1,delta=1e-12)
                        self.assertEqual(datum.secondary_voltage_v,0)
                        self.assertEqual(datum.apparent_resistivity_anomaly_ohm_m,0)
                        np.testing.assert_allclose([datum.potential_m_v,datum.potential_n_v],
                                                   sample_surface_potential(solution,[array.m_x_m,array.n_x_m]))

    def test_dipole_polarity_is_preserved(self):
        solution=solve_source_pair(np.full((8,16),.01),self.configurations[2],n_wavenumbers=8)
        datum=measure_receivers(solution)
        self.assertLess(datum.voltage_v,0)
        self.assertLess(datum.geometric_factor_m,0)
        self.assertGreater(datum.apparent_resistivity_ohm_m,0)
        self.assertAlmostEqual(datum.apparent_resistivity_ohm_m,100)

    def test_air_water_receiver_data_finite_and_reference_anomaly_consistent(self):
        for name in ('air','water'):
            for array in self.configurations:
                with self.subTest(material=name,array=array.array_type):
                    solution=self.models[name,array.array_type]
                    datum=measure_receivers(solution)
                    self.assertTrue(np.isfinite(datum.apparent_resistivity_ohm_m))
                    self.assertNotAlmostEqual(datum.secondary_voltage_v,0,places=7)
                    self.assertAlmostEqual(datum.voltage_v,datum.potential_m_v-datum.potential_n_v)
                    self.assertAlmostEqual(datum.apparent_resistivity_anomaly_ohm_m,
                                           datum.apparent_resistivity_ohm_m-100)
                    self.assertAlmostEqual(datum.relative_apparent_resistivity_anomaly,
                                           datum.apparent_resistivity_anomaly_ohm_m/100)
        # For this symmetric Wenner target, the expected contrast signs are clear.
        self.assertGreater(measure_receivers(self.models['air','wenner']).apparent_resistivity_ohm_m,100)
        self.assertLess(measure_receivers(self.models['water','wenner']).apparent_resistivity_ohm_m,100)

    def test_voltage_scales_with_current_but_apparent_resistivity_does_not(self):
        original=self.models['water','wenner']
        scaled=solve_source_pair(original.conductivity,replace(original.electrodes,current_a=.25))
        first,second=measure_receivers(original),measure_receivers(scaled)
        self.assertAlmostEqual(second.voltage_v,first.voltage_v*.25)
        self.assertAlmostEqual(second.apparent_resistivity_ohm_m,first.apparent_resistivity_ohm_m)

    def test_absolute_material_resistivity_scales_the_apparent_resistivity(self):
        original=self.models['water','wenner']
        scaled=solve_source_pair(original.conductivity/2,original.electrodes)
        first,second=measure_receivers(original),measure_receivers(scaled)
        self.assertAlmostEqual(second.voltage_v,first.voltage_v*2)
        self.assertAlmostEqual(second.apparent_resistivity_ohm_m,first.apparent_resistivity_ohm_m*2)
        self.assertAlmostEqual(second.background_resistivity_ohm_m,200)
        self.assertAlmostEqual(second.relative_apparent_resistivity_anomaly,
                               first.relative_apparent_resistivity_anomaly)

    def test_receiver_spacing_reuses_only_matching_sources(self):
        original=self.models['water','schlumberger']
        new=schlumberger(center_x_m=50,ab_half_spacing_m=20,mn_half_spacing_m=4)
        result=measure_receivers(original,electrodes=new)
        self.assertEqual(result.electrodes,new)
        sampled=sample_surface_potential(original,[new.m_x_m,new.n_x_m])
        self.assertAlmostEqual(result.voltage_v,sampled[0]-sampled[1])
        self.assertNotAlmostEqual(result.voltage_v,measure_receivers(original).voltage_v)
        for changed in (schlumberger(center_x_m=50,ab_half_spacing_m=21,mn_half_spacing_m=4),
                        replace(new,current_a=.1)):
            with self.assertRaisesRegex(ValueError,'match'):measure_receivers(original,electrodes=changed)
        outside=replace(original,x=original.x-100)
        with self.assertRaises(ValueError):measure_receivers(outside,electrodes=new)

    def test_negative_apparent_resistivity_is_not_silently_absoluted(self):
        original=self.models['water','wenner']
        # Artificial data for sign handling, not a claim about a physical tunnel.
        xx,_=np.meshgrid(original.x,original.z)
        synthetic=replace(original,secondary_potential=xx)
        datum=measure_receivers(synthetic)
        self.assertLess(datum.voltage_v,0)
        self.assertLess(datum.apparent_resistivity_ohm_m,0)

    def test_translated_domain_preserves_receiver_data(self):
        original=self.models['water','wenner']
        e=wenner(center_x_m=-50,spacing_m=10)
        shifted=replace(original,x=original.x-100,electrodes=e)
        self.assertAlmostEqual(measure_receivers(shifted).voltage_v,measure_receivers(original).voltage_v)

    def test_nonzero_surface_response_against_independent_layered_image_solution(self):
        width,height,nx,nz=480.,320.,192,128
        z=(np.arange(nz)+.5)*height/nz
        sigma=np.broadcast_to(np.where(z[:,None]<10,.01,.005),(nz,nx)).copy()
        array=wenner(center_x_m=width/2,spacing_m=10)
        solution=solve_source_pair(sigma,array,width=width,height=height)
        datum=measure_receivers(solution)
        potentials=[]
        for receiver in (array.m_x_m,array.n_x_m):
            value=0.
            for source,sign in ((array.a_x_m,1),(array.b_x_m,-1)):
                distance=abs(receiver-source)
                images=sum(2*(1/3)**n/np.hypot(distance,20*n) for n in range(1,80))
                value+=sign*100/(2*np.pi)*(1/distance+images)
            potentials.append(value)
        exact_voltage=potentials[0]-potentials[1]
        exact_secondary=exact_voltage-datum.primary_voltage_v
        self.assertGreater(exact_secondary,.01)
        self.assertLess(abs(datum.secondary_voltage_v-exact_secondary)/abs(exact_secondary),.01)
        exact_rhoa=2*np.pi*10*exact_voltage
        self.assertLess(abs(datum.apparent_resistivity_ohm_m-exact_rhoa)/exact_rhoa,.001)


if __name__=='__main__':
    unittest.main()
