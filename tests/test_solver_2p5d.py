"""Point-source physics, nonzero secondary solution, and error-source checks.

Homogeneous recovery is exact by construction; the layered-earth and forced
mode tests independently exercise the numerical correction and spatial operator.
"""
from dataclasses import replace
import unittest

import numpy as np
from scipy.sparse import diags
from scipy.sparse.linalg import spsolve
from scipy.special import k0

from tunnel_resistivity.electrodes import wenner, schlumberger, dipole_dipole
from tunnel_resistivity.geometry import circular_tunnel
from tunnel_resistivity.solver_2p5d import (
    solve_source_pair, log_wavenumber_quadrature, _assemble_operator,
)


def tunnel_model(resistivity=5., width=100., height=50.):
    return circular_tunnel(width=width, height=height, nx=round(width/1.25),
                           nz=round(height/1.25), center_x=width/2, depth=15,
                           radius=5, host_resistivity=100, tunnel_resistivity=resistivity)


class SourcePairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.array = wenner(center_x_m=50, spacing_m=10)
        cls.sigma, cls.mask = tunnel_model()
        cls.water = solve_source_pair(cls.sigma, cls.array)
        air_sigma, _ = tunnel_model(1e8)
        cls.air = solve_source_pair(air_sigma, cls.array)

    def test_homogeneous_halfspace_potential_and_current_all_arrays(self):
        arrays = (self.array,
                  schlumberger(center_x_m=50, ab_half_spacing_m=20, mn_half_spacing_m=2),
                  dipole_dipole(center_x_m=50, spacing_m=5, separation_n=2))
        for array in arrays:
            with self.subTest(array=array.array_type):
                result = solve_source_pair(np.full((20,40),.01), array, n_wavenumbers=16)
                xx, zz = np.meshgrid(result.x, result.z)
                da, db = xx-array.a_x_m, xx-array.b_x_m
                ra, rb = np.hypot(da,zz), np.hypot(db,zz)
                expected = array.current_a*100/(2*np.pi)*(1/ra-1/rb)
                np.testing.assert_allclose(result.potential, expected, rtol=1e-14, atol=1e-14)
                np.testing.assert_array_equal(result.secondary_potential,0)
                np.testing.assert_allclose(result.jx, array.current_a/(2*np.pi)*(da/ra**3-db/rb**3))
                np.testing.assert_allclose(result.jz, array.current_a/(2*np.pi)*(zz/ra**3-zz/rb**3))
                self.assertEqual(result.max_relative_mode_residual,0)

    def test_contrasting_tunnels_finite_and_current_uses_actual_material(self):
        xx, zz = np.meshgrid(self.water.x,self.water.z)
        core = (xx-50)**2+(zz-15)**2 < 2.5**2
        for result in (self.air,self.water):
            for field in (result.potential,result.jx,result.jz,result.secondary_potential):
                self.assertTrue(np.all(np.isfinite(field)))
            self.assertGreater(np.max(abs(result.secondary_potential)),.01)
            self.assertTrue(np.all(result.conductivity>0))
        # Compare the same interior cells, away from the stair-stepped interface.
        reference = solve_source_pair(np.full_like(self.sigma,.01),self.array,n_wavenumbers=8)
        background_j = np.median(np.hypot(reference.jx[core],reference.jz[core]))
        self.assertLess(np.median(np.hypot(self.air.jx[core],self.air.jz[core])),background_j*.001)
        self.assertGreater(np.median(np.hypot(self.water.jx[core],self.water.jz[core])),background_j*1.2)
        self.assertLess(np.vdot(self.air.secondary_potential,self.water.secondary_potential),0)

    def test_mode_residual_and_conservation_include_wavenumber_term(self):
        for result in (self.air,self.water):
            with self.subTest(contrast=result.conductivity.min()):
                self.assertLess(result.max_relative_mode_residual,1e-9)
                self.assertLess(result.max_relative_mode_balance_error,1e-10)
                self.assertEqual(len(result.mode_diagnostics),64)

    def test_air_limit_saturates_without_spurious_bulk_source(self):
        less_resistive,_ = tunnel_model(1e6)
        comparison = solve_source_pair(less_resistive,self.array)
        # The limiting insulating inclusion has bounded interior potential;
        # it must not amplify the primary's discretization error by rho/rho0.
        self.assertLess(np.max(abs(self.air.potential[self.mask])),1.)
        relative = np.linalg.norm(self.air.secondary_potential-comparison.secondary_potential)
        relative /= np.linalg.norm(self.air.secondary_potential)
        self.assertLess(relative,.001)

    def test_source_current_scaling(self):
        scaled = solve_source_pair(self.sigma,replace(self.array,current_a=.25),n_wavenumbers=64)
        for name in ('potential','secondary_potential','jx','jz'):
            np.testing.assert_allclose(getattr(scaled,name),.25*getattr(self.water,name),rtol=1e-10,atol=1e-12)

    def test_absolute_conductivity_scaling_for_fixed_current(self):
        scaled = solve_source_pair(2*self.sigma,self.array,background_conductivity=.02)
        np.testing.assert_allclose(scaled.potential,self.water.potential/2,atol=1e-12)
        np.testing.assert_allclose(scaled.jx,self.water.jx,rtol=1e-9,atol=1e-12)
        np.testing.assert_allclose(scaled.jz,self.water.jz,rtol=1e-9,atol=1e-12)

    def test_horizontal_symmetry_and_translated_coordinate_origin(self):
        np.testing.assert_allclose(self.water.potential,-self.water.potential[:,::-1],atol=1e-12)
        np.testing.assert_allclose(self.water.jx,self.water.jx[:,::-1],atol=1e-12)
        np.testing.assert_allclose(self.water.jz,-self.water.jz[:,::-1],atol=1e-12)
        shifted = solve_source_pair(self.sigma,wenner(center_x_m=-50,spacing_m=10),x_origin_m=-100)
        np.testing.assert_allclose(shifted.x,self.water.x-100)
        np.testing.assert_allclose(shifted.potential,self.water.potential,atol=1e-12)

    def test_wavenumber_count_and_cutoff_sensitivity(self):
        coarse = solve_source_pair(self.sigma,self.array,n_wavenumbers=24)
        medium = solve_source_pair(self.sigma,self.array,n_wavenumbers=48)
        fine = solve_source_pair(self.sigma,self.array,n_wavenumbers=72)
        norm = np.linalg.norm(fine.secondary_potential)
        coarse_change = np.linalg.norm(coarse.secondary_potential-medium.secondary_potential)/norm
        fine_change = np.linalg.norm(medium.secondary_potential-fine.secondary_potential)/norm
        self.assertLess(fine_change,1e-5)
        self.assertLess(fine_change,coarse_change/100)
        extended = solve_source_pair(self.sigma,self.array,n_wavenumbers=96,k_min=1e-10,k_max=32)
        self.assertLess(np.linalg.norm(extended.secondary_potential-fine.secondary_potential)/norm,1e-5)

    def test_domain_extension_on_matching_central_patch(self):
        patches = []
        for width,height in ((100,50),(200,100),(300,150)):
            sigma,_ = tunnel_model(width=width,height=height)
            result = solve_source_pair(sigma,wenner(center_x_m=width/2,spacing_m=10),
                                       width=width,height=height,k_min=1e-8,k_max=16)
            keep_x = abs(result.x-width/2)<20
            patches.append(result.secondary_potential[result.z<30][:,keep_x])
        first = np.linalg.norm(patches[1]-patches[0])
        last = np.linalg.norm(patches[2]-patches[1])
        self.assertLess(last,first)
        self.assertLess(last/np.linalg.norm(patches[2]),.01)

    def test_invalid_conductivity_shape_values_and_surface_anomaly(self):
        for value in (np.ones(10), np.ones((1,4)), np.empty((0,4)),
                      np.full((4,4),0), np.full((4,4),-1),np.full((4,4),np.nan),
                      np.full((4,4),np.inf),np.full((4,4),1+1j)):
            with self.subTest(shape=np.shape(value)),self.assertRaises(ValueError):
                solve_source_pair(value,self.array)
        sigma=np.full((4,4),.01);sigma[0,1]=.02
        with self.assertRaisesRegex(ValueError,'top row'):
            solve_source_pair(sigma,self.array)
        with self.assertRaisesRegex(ValueError,'top row'):
            solve_source_pair(np.full((4,4),.01),self.array,background_conductivity=.02)

    def test_invalid_domain_source_and_background(self):
        sigma=np.full((4,8),.01)
        for params in ({'width':0},{'height':-1},{'x_origin_m':np.nan},
                       {'background_conductivity':0},{'background_conductivity':np.inf},
                       {'width':30},{'x_origin_m':100}):
            with self.subTest(params=params), self.assertRaises(ValueError):
                solve_source_pair(sigma,self.array,**params)
        with self.assertRaises(ValueError): solve_source_pair(sigma,None)


class IndependentNumericalChecks(unittest.TestCase):
    def test_fourier_normalization_against_known_bessel_integral(self):
        # Independently known identity: integral_0^infinity K0(kr) dk = pi/(2r).
        ks, weights = log_wavenumber_quadrature(n_wavenumbers=96,k_min=1e-10,k_max=80)
        for r in (.5,1,5,20):
            with self.subTest(r=r):
                reconstructed = np.sum(weights*k0(ks*r))/np.pi
                self.assertAlmostEqual(reconstructed/(1/(2*r)),1,delta=1e-7)

    def test_invalid_fourier_parameters(self):
        for params in ({'n_wavenumbers':7},{'n_wavenumbers':513},{'n_wavenumbers':32.},
                       {'n_wavenumbers':True},{'k_min':0},{'k_min':-1},
                       {'k_max':np.inf},{'k_max':1e-12}):
            config=dict(n_wavenumbers=64,k_min=1e-8,k_max=10);config.update(params)
            with self.subTest(params=params),self.assertRaises(ValueError):
                log_wavenumber_quadrature(**config)

    def test_forced_fourier_mode_second_order_spatial_convergence(self):
        errors=[]
        for nx in (16,32,64):
            width,height=20,10;nz=nx//2;dx=width/nx;dz=height/nz;k=.2
            sigma=np.full((nz,nx),.01)
            xx,zz=np.meshgrid((np.arange(nx)+.5)*dx,(np.arange(nz)+.5)*dz)
            exact=np.sin(np.pi*xx/width)*np.cos(np.pi*zz/(2*height))
            base,mass,_=_assemble_operator(sigma,dx,dz)
            # Manufactured forcing from continuous -sigma Laplacian(u)+k² sigma u.
            rhs=mass*((np.pi/width)**2+(np.pi/(2*height))**2+k*k)*exact.ravel()
            values=spsolve(base+diags(k*k*mass),rhs).reshape(sigma.shape)
            errors.append(np.sqrt(np.mean((values-exact)**2)))
        orders=np.log2(np.array(errors[:-1])/errors[1:])
        self.assertTrue(np.all((orders>1.95)&(orders<2.05)),orders)

    def test_piecewise_conductivity_harmonic_flux_and_boundaries(self):
        width,height,nx,nz=20,10,40,20;dx=width/nx;dz=height/nz
        x=(np.arange(nx)+.5)*dx
        # Independent 1D series-resistance solution, insulated top.
        sigma=np.tile(np.where(x<10,.01,.001),(nz,1))
        current=1/(10/.01+10/.001)
        exact=1-current*(np.minimum(x,10)/.01+np.maximum(x-10,0)/.001)
        base,_,_=_assemble_operator(sigma,dx,dz)
        rhs=np.zeros_like(sigma)
        rhs[:,0]+=2*sigma[:,0]*dz/dx  # Vleft=1, Vright=0.
        rhs[-1,:]+=2*sigma[-1,:]*dx/dz*exact
        numerical=spsolve(base,rhs.ravel()).reshape(sigma.shape)
        np.testing.assert_allclose(numerical,np.tile(exact,(nz,1)),atol=1e-13)
        # Independent face resistance calculation across the material jump.
        flux=(numerical[:,:-1]-numerical[:,1:])/(dx/(2*sigma[:,:-1])+dx/(2*sigma[:,1:]))
        np.testing.assert_allclose(flux,current,rtol=1e-11)

    def test_layered_halfspace_against_independent_image_series(self):
        width,height,nx,nz=480,320,192,128
        xx,zz=np.meshgrid((np.arange(nx)+.5)*width/nx,(np.arange(nz)+.5)*height/nz)
        sigma=np.where(zz<10,.01,.005)
        array=wenner(center_x_m=width/2,spacing_m=10)
        result=solve_source_pair(sigma,array,width=width,height=height)
        exact=np.zeros_like(sigma)
        for source,sign in ((array.a_x_m,1),(array.b_x_m,-1)):
            term=1/np.hypot(xx-source,zz)
            # rho1=100, rho2=200, h=10; image reflection coefficient = 1/3.
            for n in range(1,80):
                term+=(1/3)**n*(1/np.hypot(xx-source,zz-20*n)+1/np.hypot(xx-source,zz+20*n))
            exact+=sign*100/(2*np.pi)*term
        keep=(abs(xx-width/2)<10)&(zz<5)  # upper layer, away from electrodes
        correction=(exact-result.primary_potential)[keep]
        self.assertGreater(np.linalg.norm(correction),.01)
        relative=np.linalg.norm(result.potential[keep]-exact[keep])/np.linalg.norm(correction)
        self.assertLess(relative,.01)  # mesh + artificial-boundary error, not residual


if __name__=='__main__':
    unittest.main()
