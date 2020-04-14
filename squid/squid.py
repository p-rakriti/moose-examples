# Filename: squid.py
# Description:
# Author: Subhasis Ray
# Maintainer: Dilawar Singh

import sys
import numpy as np
import moose

GAS_CONSTANT = 8.314
FARADAY = 9.65e4
CELSIUS_TO_KELVIN = 273.15


class IonChannel(object):
    """Enhanced version of HHChannel with setupAlpha that takes a dict
    of parameters."""
    def __init__(self,
                 name,
                 compartment,
                 specific_gbar,
                 e_rev,
                 Xpower,
                 Ypower=0.0,
                 Zpower=0.0):
        """Instantuate an ion channel.

        name -- name of the channel.
        
        compartment -- moose.Compartment object that contains the channel.

        specific_gbar -- specific value of maximum conductance.

        e_rev -- reversal potential of the channel.
        
        Xpower -- exponent for the first gating parameter.

        Ypower -- exponent for the second gatinmg component.
        """
        self.path = "%s/%s" % (compartment.path, name)
        self.chan = moose.HHChannel(self.path)
        self.chan.Gbar = specific_gbar * compartment.area()
        self.chan.Ek = e_rev
        self.chan.Xpower = Xpower
        self.chan.Ypower = Ypower
        self.chan.Zpower = Zpower
        moose.connect(self.chan, "channel", compartment.compt, "channel")

    def setupAlpha(self, gate, params, vdivs, vmin, vmax):
        """Setup alpha and beta parameters of specified gate.

        gate -- 'X'/'Y'/'Z' string initial of the gate.

        params -- dict of parameters to compute alpha and beta, the rate constants for gates.

        vdivs -- number of divisions in the interpolation tables for alpha and beta parameters.

        vmin -- minimum voltage value for the alpha/beta lookup tables.

        vmax -- maximum voltage value for the alpha/beta lookup tables.
        """
        if gate == "X" and self.chan.Xpower > 0:
            gate = moose.HHGate(self.path + "/gateX")
        elif gate == "Y" and self.chan.Ypower > 0:
            gate = moose.HHGate(self.path + "/gateY")
        else:
            return False
        gate.setupAlpha([
            params["A_A"],
            params["A_B"],
            params["A_C"],
            params["A_D"],
            params["A_F"],
            params["B_A"],
            params["B_B"],
            params["B_C"],
            params["B_D"],
            params["B_F"],
            vdivs,
            vmin,
            vmax,
        ])
        return True

    def get_alpha_m(self):
        if self.chan.Xpower == 0:
            return np.array([])
        return np.array(moose.element("%s/gateX" % (self.path)).tableA)

    def get_beta_m(self):
        if self.chan.Xpower == 0:
            return np.array([])
        return np.array(moose.element("%s/gateX" %
                                      (self.path)).tableB) - np.array(
                                          moose.element("%s/gateX" %
                                                        (self.path)).tableA)

    def get_alpha_h(self):
        if self.chan.Ypower == 0:
            return np.array([])
        return np.array(moose.element("%s/gateY" % (self.path)).tableA)

    def get_beta_h(self):
        if self.chan.Ypower == 0:
            return np.array([])
        return np.array(moose.element("%s/gateY" %
                                      (self.path)).tableB) - np.array(
                                          moose.element("%s/gateY" %
                                                        (self.path)).tableA)


class SquidAxon(object):
    EREST_ACT = 0.0  # can be -70 mV if not following original HH convention
    VMIN = -30.0
    VMAX = 120.0
    VDIVS = 150
    defaults = {
        "temperature": CELSIUS_TO_KELVIN + 6.3,
        "K_out": 10.0,
        "Na_out": 460.0,
        "K_in": 301.4,
        "Na_in": 70.97,
        "Cl_out": 540.0,
        "Cl_in": 100.0,
        "length": 500.0,  # um
        "diameter": 500.0,  # um
        "Em": EREST_ACT + 10.613,
        "initVm": EREST_ACT,
        "specific_cm": 1.0,  # uF/cm^2
        "specific_gl": 0.3,  # mmho/cm^2
        "specific_ra": 0.030,  # kohm-cm
        "specific_gNa": 120.0,  # mmho/cm^2
        "specific_gK": 36.0,  # mmho/cm^2
    }

    Na_m_params = {
        "A_A": 0.1 * (25.0 + EREST_ACT),
        "A_B": -0.1,
        "A_C": -1.0,
        "A_D": -25.0 - EREST_ACT,
        "A_F": -10.0,
        "B_A": 4.0,
        "B_B": 0.0,
        "B_C": 0.0,
        "B_D": 0.0 - EREST_ACT,
        "B_F": 18.0,
    }
    Na_h_params = {
        "A_A": 0.07,
        "A_B": 0.0,
        "A_C": 0.0,
        "A_D": 0.0 - EREST_ACT,
        "A_F": 20.0,
        "B_A": 1.0,
        "B_B": 0.0,
        "B_C": 1.0,
        "B_D": -30.0 - EREST_ACT,
        "B_F": -10.0,
    }
    K_n_params = {
        "A_A": 0.01 * (10.0 + EREST_ACT),
        "A_B": -0.01,
        "A_C": -1.0,
        "A_D": -10.0 - EREST_ACT,
        "A_F": -10.0,
        "B_A": 0.125,
        "B_B": 0.0,
        "B_C": 0.0,
        "B_D": 0.0 - EREST_ACT,
        "B_F": 80.0,
    }
    """Compartment class enhanced with specific values of passive
    electrical properties set and calculated using dimensions."""
    def __init__(self, path):
        self.path = path
        self.compt = moose.Compartment(self.path)
        self.temperature = SquidAxon.defaults["temperature"]
        self.K_out = SquidAxon.defaults["K_out"]
        self.Na_out = SquidAxon.defaults["Na_out"]
        # Modified internal concentrations used to give HH values of
        # equilibrium constants from the Nernst equation at 6.3 deg C.
        # HH 1952a, p. 455
        self.K_in = SquidAxon.defaults["K_in"]
        self.Na_in = SquidAxon.defaults["Na_in"]
        self.Cl_out = SquidAxon.defaults["Cl_out"]
        self.Cl_in = SquidAxon.defaults["Cl_in"]

        self.compt.length = SquidAxon.defaults["length"]
        self.compt.diameter = SquidAxon.defaults["diameter"]
        self.compt.Em = SquidAxon.defaults["Em"]
        self.compt.initVm = SquidAxon.defaults["initVm"]

        self.specific_cm = SquidAxon.defaults["specific_cm"]
        self.specific_gl = SquidAxon.defaults["specific_gl"]
        self.specific_ra = SquidAxon.defaults["specific_ra"]

        self.Na_channel = IonChannel("Na",
                                     self,
                                     0.0,
                                     self.get_VNa(),
                                     Xpower=3.0,
                                     Ypower=1.0)

        self.Na_channel.setupAlpha("X", SquidAxon.Na_m_params, SquidAxon.VDIVS,
                                   SquidAxon.VMIN, SquidAxon.VMAX)

        self.Na_channel.setupAlpha("Y", SquidAxon.Na_h_params, SquidAxon.VDIVS,
                                   SquidAxon.VMIN, SquidAxon.VMAX)

        self.K_channel = IonChannel("K", self, 0.0, self.get_VK(), Xpower=4.0)

        self.K_channel.setupAlpha("X", SquidAxon.K_n_params, SquidAxon.VDIVS,
                                  SquidAxon.VMIN, SquidAxon.VMAX)

        self.specific_gNa = SquidAxon.defaults["specific_gNa"]
        self.specific_gK = SquidAxon.defaults["specific_gK"]

    @classmethod
    def reversal_potential(cls, temp, c_out, c_in):
        """Compute the reversal potential based on Nernst equation."""
        # NOTE the 70 mV added for compatibility with original HH
        v = ((GAS_CONSTANT * temp / FARADAY) * 1000.0 * np.log(c_out / c_in) +
             70.0 + cls.EREST_ACT)
        return v

    def xarea(self):
        """Area of cross section in cm^2 when length and diameter are in um"""
        return 1e-8 * np.pi * self.compt.diameter * self.compt.diameter / 4.0  # cm^2

    def area(self):
        """Area in cm^2 when length and diameter are in um"""
        return 1e-8 * self.compt.length * np.pi * self.compt.diameter  # cm^2

    def get_specific_ra(self):
        return self.compt.Ra * self.xarea() / self.compt.length

    def set_specific_ra(self, value):
        self.compt.Ra = value * self.compt.length / self.xarea()

    specific_ra = property(get_specific_ra, set_specific_ra)

    def get_specific_cm(self):
        return self.compt.Cm / self.area()

    def set_specific_cm(self, value):
        self.compt.Cm = value * self.area()

    specific_cm = property(get_specific_cm, set_specific_cm)

    def get_specific_gl(self):
        return 1.0 / (self.compt.Rm * self.area())

    def set_specific_gl(self, value):
        self.compt.Rm = 1.0 / (value * self.area())

    specific_gl = property(get_specific_gl, set_specific_gl)

    def get_specific_rm(self):
        return self.compt.Rm * self.area()

    def set_specific_rm(self, value):
        self.compt.Rm = value / self.area()

    specific_rm = property(get_specific_rm, set_specific_rm)

    def get_specific_gNa(self):
        return self.Na_channel.Gbar / self.area()

    def set_specific_gNa(self, value):
        self.Na_channel.Gbar = value * self.area()

    specific_gNa = property(get_specific_gNa, set_specific_gNa)


    def get_specific_gK(self):
        return self.K_channel.Gbar / self.area()

    def set_specific_gK(self, value):
        self.K_channel.Gbar = value * self.area()

    specific_gK = property(get_specific_gK, set_specific_gK)

    def get_VK(self):
        """Reversal potential of K+ channels"""
        return SquidAxon.reversal_potential(self.temperature, self.K_out, self.K_in)

    def get_VNa(self):
        """Reversal potential of Na+ channels"""
        return SquidAxon.reversal_potential(self.temperature, self.Na_out,
                                            self.Na_in)

    def updateEk(self):
        """Update the channels' Ek"""
        self.Na_channel.Ek = self.get_VNa()
        self.K_channel.Ek = self.get_VK()

    def get_celsius(self):
        return self.temperature - CELSIUS_TO_KELVIN

    def set_celsius(self, celsius):
        self.temperature = celsius + CELSIUS_TO_KELVIN

    celsius = property(get_celsius, set_celsius)


class SquidModel:
    """Container for squid demo."""
    def __init__(self, path):
        self.path = path
        moose.Neutral(self.path)
        self.squid = SquidAxon(path + "/squidAxon")
        self.current_clamp = moose.PulseGen(path + "/pulsegen")
        self.current_clamp.firstDelay = 5.0  # ms
        self.current_clamp.firstWidth = 40  # ms
        self.current_clamp.firstLevel = 0.1  # uA
        self.current_clamp.secondDelay = 1e9
        moose.connect(self.current_clamp, "output", self.squid.compt,
                      "injectMsg")

        self.Vm_table = moose.Table("%s/Vm" % (self.path))
        moose.connect(self.Vm_table, "requestOut", self.squid.compt, "getVm")
        self.gK_table = moose.Table("%s/gK" % (self.path))
        moose.connect(self.gK_table, "requestOut", self.squid.K_channel.chan,
                      "getGk")
        self.gNa_table = moose.Table("%s/gNa" % (self.path))
        moose.connect(self.gNa_table, "requestOut", self.squid.Na_channel.chan,
                      "getGk")
        self.clocks_assigned = False

    def run(self, runtime, simdt=1e-6):
        self.squid.updateEk()
        moose.reinit()
        moose.start(runtime)

    def plot_data(self):
        import matplotlib.pyplot as plt

        ax11 = plt.subplot(221)
        ax12 = plt.subplot(222)
        ax21 = plt.subplot(223)
        ax22 = plt.subplot(224)
        ax11.plot(self.Vm_table.vector)

        ax12.plot(self.gNa_table.vector)
        ax12.plot(self.gK_table.vector)

        plt.show()


def test(runtime=100.0, simdt=1e-2):
    model = SquidModel("/model")
    model.run(runtime, simdt)
    #  model.save_data()
    model.plot_data()


if __name__ == "__main__":
    test()
