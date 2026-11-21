"""Independent distance/order checks for the future survey geometry."""

from dataclasses import FrozenInstanceError
import unittest

import numpy as np

from tunnel_resistivity.electrodes import ElectrodeArray, wenner, schlumberger, dipole_dipole


class ElectrodeGeometryTests(unittest.TestCase):
    def test_wenner_coordinates_order_and_three_equal_intervals(self):
        config = wenner(center_x_m=50, spacing_m=5, current_a=.1)
        self.assertEqual(config.positions_x_m, {'A':42.5,'B':57.5,'M':47.5,'N':52.5})
        np.testing.assert_allclose(np.diff(sorted(config.positions_x_m.values())), 5)
        self.assertEqual(config.span_m, 15)
        self.assertEqual(config.center_x_m, 50)

    def test_schlumberger_independent_pair_spacings(self):
        config = schlumberger(center_x_m=50, ab_half_spacing_m=20, mn_half_spacing_m=2)
        self.assertEqual(config.positions_x_m, {'A':30,'B':70,'M':48,'N':52})
        self.assertEqual(config.b_x_m-config.a_x_m, 40)
        self.assertEqual(config.n_x_m-config.m_x_m, 4)
        self.assertEqual((config.a_x_m+config.b_x_m)/2, (config.m_x_m+config.n_x_m)/2)

    def test_dipole_dipole_gap_is_n_times_dipole_length(self):
        for n in (1,2,3,10):
            with self.subTest(n=n):
                config = dipole_dipole(center_x_m=50, spacing_m=5, separation_n=n)
                self.assertEqual(config.b_x_m-config.a_x_m, 5)
                self.assertEqual(config.n_x_m-config.m_x_m, 5)
                self.assertEqual(config.m_x_m-config.b_x_m, n*5)
                self.assertEqual(config.span_m, (n+2)*5)
                self.assertEqual(config.center_x_m, 50)
                self.assertLess(config.a_x_m,config.b_x_m)
                self.assertLess(config.b_x_m,config.m_x_m)
                self.assertLess(config.m_x_m,config.n_x_m)

    def test_source_return_balance_and_current_units(self):
        for factory in (lambda:wenner(center_x_m=20,spacing_m=2,current_a=.05),
                        lambda:schlumberger(center_x_m=20,ab_half_spacing_m=8,mn_half_spacing_m=1,current_a=.05),
                        lambda:dipole_dipole(center_x_m=20,spacing_m=2,current_a=.05)):
            config=factory()
            self.assertEqual(config.source_currents_a, {'A':.05,'B':-.05})
            self.assertEqual(sum(config.source_currents_a.values()),0)

    def test_translations_preserve_every_pair_distance(self):
        for factory in (lambda c:wenner(center_x_m=c,spacing_m=2.5),
                        lambda c:schlumberger(center_x_m=c,ab_half_spacing_m=10,mn_half_spacing_m=1.5),
                        lambda c:dipole_dipole(center_x_m=c,spacing_m=2.5,separation_n=3)):
            first, shifted = factory(0), factory(37.25)
            for name in first.positions_x_m:
                self.assertAlmostEqual(shifted.positions_x_m[name]-first.positions_x_m[name],37.25)

    def test_bad_scalar_inputs_are_rejected(self):
        for value in (0,-1,np.nan,np.inf,-np.inf,True,'5',None,1+2j):
            for factory in (lambda:wenner(center_x_m=50,spacing_m=value),
                            lambda:dipole_dipole(center_x_m=50,spacing_m=value),
                            lambda:schlumberger(center_x_m=50,ab_half_spacing_m=value,mn_half_spacing_m=1)):
                with self.subTest(value=value), self.assertRaises(ValueError): factory()
        for c in (np.nan,np.inf,True,None):
            with self.subTest(center=c), self.assertRaises(ValueError):
                wenner(center_x_m=c,spacing_m=5)

    def test_bad_source_current_rejected(self):
        for current in (0,-1,np.nan,np.inf,True,'1',None):
            with self.subTest(current=current), self.assertRaises(ValueError):
                wenner(center_x_m=50,spacing_m=5,current_a=current)

    def test_schlumberger_invalid_separation(self):
        for ab,mn in ((10,10),(10,11),(10,0),(10,-1),(10,np.nan)):
            with self.subTest(ab=ab,mn=mn), self.assertRaises(ValueError):
                schlumberger(center_x_m=50,ab_half_spacing_m=ab,mn_half_spacing_m=mn)

    def test_dipole_separation_must_be_positive_integer(self):
        for n in (0,-1,1.5,2.0,True,np.nan,np.inf,'2',None):
            with self.subTest(n=n), self.assertRaises(ValueError):
                dipole_dipole(center_x_m=50,spacing_m=5,separation_n=n)
        config=dipole_dipole(center_x_m=50,spacing_m=np.float64(5),separation_n=np.int64(2))
        self.assertEqual(config.span_m,20)

    def test_domain_and_padding_validation(self):
        config=wenner(center_x_m=50,spacing_m=10)
        config.validate_domain(0,100,boundary_padding_m=35)
        for lower,upper,padding in ((0,100,36),(35,100,0),(0,65,0),(40,100,0),
                                    (100,0,0),(0,0,0),(0,np.inf,0),(0,100,-1),(0,100,np.nan)):
            with self.subTest(bounds=(lower,upper,padding)), self.assertRaises(ValueError):
                config.validate_domain(lower,upper,boundary_padding_m=padding)

    def test_invalid_direct_construction(self):
        cases=(('other',0,3,1,2), ('wenner',0,3,0,2), ('wenner',0,4,1,2),
               ('schlumberger',0,8,1,6), ('schlumberger',0,8,6,1),
               ('dipole-dipole',0,1,3,5), ('dipole-dipole',0,1,2.5,3.5),
               ('dipole-dipole',0,2,3,5))
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError): ElectrodeArray(*case)

    def test_not_snapped_to_existing_grid(self):
        config=wenner(center_x_m=50.123,spacing_m=1.234)
        self.assertAlmostEqual(config.m_x_m,49.506)
        self.assertAlmostEqual(config.n_x_m,50.740)

    def test_immutable_and_returned_dict_is_not_internal_state(self):
        config=wenner(center_x_m=50,spacing_m=5)
        with self.assertRaises(FrozenInstanceError):config.current_a=2
        positions=config.positions_x_m;positions['A']=999
        self.assertEqual(config.a_x_m,42.5)

    def test_unrepresentable_spacings_and_overflow_rejected(self):
        for center,spacing in ((1e20,1e-6),(0,1.7e308)):
            with self.subTest(center=center), self.assertRaises(ValueError):
                wenner(center_x_m=center,spacing_m=spacing)
        with self.assertRaises(ValueError):
            dipole_dipole(center_x_m=0,spacing_m=1,separation_n=10**1000)


if __name__=='__main__':
    unittest.main()
