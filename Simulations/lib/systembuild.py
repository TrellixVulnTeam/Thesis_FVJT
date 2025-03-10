"""

Author: Francisco Branco
Created: 10/05/2020
Description: ATTENTION DEPRECATED FILE

"""


import numpy as np
from math import pi
import pathgeneration as pg
import lib.kinematics as kn
import lib.pathfollowing as pf
import lib.cooperativepathfollowing as cpf
import lib.movingpathfollowing as mpf
import lib.extendedkalmanfilter as ekf
import lib.complementaryfilter as cf




class SimpleAUVPathFollowing:
    def __init__(self, some_path, gamma=1, k1=1, k2=1, k_delta=1, theta_a=1/pi, history=False, dt=1):
        self.dt = dt
        
        self.inputs = {"velocity": 0, "velocity_dot": 0}
        self.time = []
        
        self.history = history
        if history:
            state_history = True
            self.past_inputs = {
                "velocity": [],
                "velocity_dot": []
                }
            self.past_outputs = {
                "x": [],
                "y": [],
                "theta_m": [],
                "u": [],
                "s": [],
                "s1": [],
                "y1": []
                }
        else:
            state_history = False

        self.kine = kn.Kinematics(saturate=1.5, state_history=state_history, dt=dt)
        self.pf_control = pf.Lapierre(some_path=some_path, gamma=gamma, k1=k1, k2=k2, k_delta=k_delta, theta_a=theta_a, state_history=state_history, dt=dt)

    def update(self, t, inputs=None):
        if inputs is not None:
            self.inputs = inputs.copy()
        
        inputs_kine, outputs_kine = self.kine.inputs_outputs()
        inputs_pf, outputs_pf = self.pf_control.inputs_outputs()

        for key in inputs_kine.keys():
            if key in self.inputs.keys():
                inputs_kine[key] = self.inputs[key]
            if key in outputs_kine.keys():
                inputs_kine[key] = outputs_kine[key]
            if key in outputs_pf.keys():
                inputs_kine[key] = outputs_pf[key]
                
        for key in inputs_pf.keys():
            if key in self.inputs.keys():
                inputs_pf[key] = self.inputs[key]
            if key in outputs_kine.keys():
                inputs_pf[key] = outputs_kine[key]
            if key in outputs_pf.keys():
                inputs_pf[key] = outputs_pf[key]

        # Update the system
        self.kine.auv_update(inputs_kine, dt=self.dt)
        self.pf_control.pf_update(inputs_pf, dt=self.dt)

        _, outputs = self.kine.inputs_outputs()
        _, aux = self.pf_control.inputs_outputs()
        outputs.update(aux)

        if self.history:
            # Save outputs for plotting
            for key in self.past_inputs.keys():
                self.past_inputs[key].append(self.inputs[key])
            for key in self.past_outputs.keys():
                self.past_outputs[key].append(outputs[key])

        self.time.append(t)

        return outputs

    def set_initial_conditions(self, init_cond):
        self.kine.set_initial_conditions(init_cond["x"], init_cond["y"], init_cond["theta_m"])
        self.pf_control.set_initial_conditions(init_cond["s"])

    def past_values(self):
        return (self.past_outputs, self.past_inputs, self.kine.past_state, self.pf_control.past_state)




class DoubleAUVCPFContinuousCommunications:
    def __init__(self, path1, path2, k_csi=1, cpf_params=None, gamma=1, k1=1, k2=1, k_delta=1, theta_a=1/pi, history=False, dt=1):
        self.dt = dt
        
        #self.inputs = {"velocity": 0, "velocity_dot": 0}
        self.time = []
        
        self.history = history
        if history:
            state_history = True
            self.past_outputs = {
                "x0": [],
                "y0": [],
                "theta_m0": [],
                "velocity0": [],
                "s0": [],
                "u0": [],
                "velocity_dot0": [],
                "x1": [],
                "y1": [],
                "theta_m1": [],
                "velocity1": [],
                "s1": [],
                "u1": [],
                "velocity_dot1": []
                }
        else:
            state_history = False

        A_matrix = np.array([[0, 1],[1, 0]])

        self.kine0 = kn.Kinematics(saturate=0, state_history=state_history, dt=dt)
        self.pf_control0 = pf.Lapierre(some_path=path1, gamma=gamma, k1=k1, k2=k2, k_delta=k_delta, theta_a=theta_a, state_history=state_history, dt=dt)
        self.cpf_control0 = cpf.CPFContinuousController(num_auv=2, id=0, k_csi=k_csi, params=cpf_params, A_matrix=A_matrix, state_history=True, dt=dt)

        self.kine1 = kn.Kinematics(saturate=0, state_history=state_history, dt=dt)
        self.pf_control1 = pf.Lapierre(some_path=path2, gamma=gamma, k1=k1, k2=k2, k_delta=k_delta, theta_a=theta_a, state_history=state_history, dt=dt)
        self.cpf_control1 = cpf.CPFContinuousController(num_auv=2, id=1, k_csi=k_csi, params=cpf_params, A_matrix=A_matrix, state_history=True, dt=dt)

    def update(self, t):
        # Get dictionaries setup
        inputs_kine0, outputs_kine0 = self.kine0.inputs_outputs()
        inputs_pf0, outputs_pf0 = self.pf_control0.inputs_outputs()
        inputs_cpf0, outputs_cpf0 = self.cpf_control0.inputs_outputs()

        inputs_kine1, outputs_kine1 = self.kine1.inputs_outputs()
        inputs_pf1, outputs_pf1 = self.pf_control1.inputs_outputs()
        inputs_cpf1, outputs_cpf1 = self.cpf_control1.inputs_outputs()

        self.cpf_control0.inputs["gamma0"] = outputs_pf0["s"]
        self.cpf_control0.inputs["gamma1"] = outputs_pf1["s"]

        self.cpf_control1.inputs["gamma0"] = outputs_pf0["s"]
        self.cpf_control1.inputs["gamma1"] = outputs_pf1["s"]

        inputs_cpf0, outputs_cpf0 = self.cpf_control0.inputs_outputs()
        inputs_cpf1, outputs_cpf1 = self.cpf_control1.inputs_outputs()

        # Connection of variables
        # First AUV
        inputs_kine0["u"] = outputs_pf0["u"]
        inputs_kine0["velocity"] = outputs_cpf0["velocity"]
        inputs_kine0["velocity_dot"] = outputs_cpf0["velocity_dot"]
        
        inputs_pf0["x"] = outputs_kine0["x"]
        inputs_pf0["y"] = outputs_kine0["y"]
        inputs_pf0["theta_m"] = outputs_kine0["theta_m"]
        inputs_pf0["velocity"] = outputs_cpf0["velocity"]
        inputs_pf0["velocity_dot"] = outputs_cpf0["velocity_dot"]

        

        # Second AUV
        inputs_kine1["u"] = outputs_pf1["u"]
        inputs_kine1["velocity"] = outputs_cpf1["velocity"]
        inputs_kine1["velocity_dot"] = outputs_cpf1["velocity_dot"]
        
        inputs_pf1["x"] = outputs_kine1["x"]
        inputs_pf1["y"] = outputs_kine1["y"]
        inputs_pf1["theta_m"] = outputs_kine1["theta_m"]
        inputs_pf1["velocity"] = outputs_cpf1["velocity"]
        inputs_pf1["velocity_dot"] = outputs_cpf1["velocity_dot"]

        


        outputs = {}
        outputs["x0"] = outputs_kine0["x"]
        outputs["y0"] = outputs_kine0["y"]
        outputs["theta_m0"] = outputs_kine0["theta_m"]
        outputs["x1"] = outputs_kine1["x"]
        outputs["y1"] = outputs_kine1["y"]
        outputs["theta_m1"] = outputs_kine1["theta_m"]
        outputs["s0"] = outputs_pf0["s"]
        outputs["u0"] = outputs_pf0["u"]
        outputs["s1"] = outputs_pf1["s"]
        outputs["u1"] = outputs_pf1["u"]
        outputs["velocity0"] = outputs_cpf0["velocity"]
        outputs["velocity_dot0"] = outputs_cpf0["velocity_dot"]
        outputs["velocity1"] = outputs_cpf1["velocity"]
        outputs["velocity_dot1"] = outputs_cpf1["velocity_dot"]

        # Save outputs for plotting
        if self.history:
            for key in self.past_outputs.keys():
                self.past_outputs[key].append(outputs[key])

        self.time.append(t)



        # Update the system
        self.kine0.auv_update(inputs_kine0, dt=self.dt)
        self.pf_control0.pf_update(inputs_pf0, dt=self.dt)
        self.kine1.auv_update(inputs_kine1, dt=self.dt)
        self.pf_control1.pf_update(inputs_pf1, dt=self.dt)

        """
        # Fetch values to register them and maybe plot
        _, outputs_kine0 = self.kine0.inputs_outputs()
        _, outputs_pf0 = self.pf_control0.inputs_outputs()
        _, outputs_kine1 = self.kine1.inputs_outputs()
        _, outputs_pf1 = self.pf_control1.inputs_outputs()
        
        self.cpf_control0.inputs["gamma0"] = outputs_pf0["s"]
        self.cpf_control0.inputs["gamma1"] = outputs_pf1["s"]
        _, outputs_cpf0 = self.cpf_control0.inputs_outputs()
        self.cpf_control1.inputs["gamma0"] = outputs_pf0["s"]
        self.cpf_control1.inputs["gamma1"] = outputs_pf1["s"]
        _, outputs_cpf1 = self.cpf_control1.inputs_outputs()
        """
        
        
        return outputs

    def set_initial_conditions(self, init_cond):
        self.kine0.set_initial_conditions(init_cond["x0"], init_cond["y0"], init_cond["theta_m0"])
        self.pf_control0.set_initial_conditions(init_cond["s0"])

        self.kine1.set_initial_conditions(init_cond["x1"], init_cond["y1"], init_cond["theta_m1"])
        self.pf_control1.set_initial_conditions(init_cond["s1"])

        gammas = {"gamma0": init_cond["s0"], "gamma1": init_cond["s1"]}
        self.cpf_control0.set_initial_conditions(gammas)
        self.cpf_control1.set_initial_conditions(gammas)

    def past_values(self):
        return (self.past_outputs, self.kine0.past_state, self.pf_control0.past_state, self.kine1.past_state, self.pf_control1.past_state)




class DoubleAUVCPFETC:
    def __init__(self, path0, path1, k_csi=1, gamma=1, k1=1, k2=1, k_delta=1, theta_a=1/pi, speed_profile=1, params=None, etc_type="Time", history=False, dt=1):
        self.dt = dt
        
        #self.inputs = {"velocity": 0, "velocity_dot": 0}
        self.time = []
        
        self.history = history
        if history:
            state_history = True
            self.past_outputs = {
                "x0": [],
                "y0": [],
                "theta_m0": [],
                "velocity0": [],
                "s0": [],
                "u0": [],
                "velocity_dot0": [],
                "gamma00": [],
                "gamma01": [],
                "x1": [],
                "y1": [],
                "theta_m1": [],
                "velocity1": [],
                "s1": [],
                "u1": [],
                "velocity_dot1": [],
                "gamma10": [],
                "gamma11": [],
            }
        else:
            state_history = False

        A_matrix = np.array([[0, 1],[1, 0]])

        self.kine0 = kn.Kinematics(saturate=0, state_history=state_history, dt=dt)
        self.pf_control0 = pf.Lapierre(some_path=path0, gamma=gamma, k1=k1, k2=k2, k_delta=k_delta, theta_a=theta_a, state_history=state_history, dt=dt)
        self.cpf_control0 = cpf.CPFDiscreteControllerETC(num_auv=2, id=0, params=params, k_csi=k_csi, A_matrix=A_matrix, etc_type=etc_type, state_history=state_history, dt=1)
        
        self.kine1 = kn.Kinematics(saturate=0, state_history=state_history, dt=dt)
        self.pf_control1 = pf.Lapierre(some_path=path1, gamma=gamma, k1=k1, k2=k2, k_delta=k_delta, theta_a=theta_a, state_history=state_history, dt=dt)
        self.cpf_control1 = cpf.CPFDiscreteControllerETC(num_auv=2, id=1, params=params, k_csi=k_csi, A_matrix=A_matrix, etc_type=etc_type, state_history=state_history, dt=1)
        
    def update(self, t):
        
        # Get dictionaries setup
        inputs_kine0, outputs_kine0 = self.kine0.inputs_outputs()
        inputs_pf0, outputs_pf0 = self.pf_control0.inputs_outputs()
        inputs_cpf0, outputs_cpf0 = self.cpf_control0.inputs_outputs()

        inputs_kine1, outputs_kine1 = self.kine1.inputs_outputs()
        inputs_pf1, outputs_pf1 = self.pf_control1.inputs_outputs()
        inputs_cpf1, outputs_cpf1 = self.cpf_control1.inputs_outputs()

        

        self.cpf_control0.inputs["gamma0"] = outputs_pf0["s"]
        self.cpf_control1.inputs["gamma1"] = outputs_pf1["s"]




        # Check if comms needs update
        broadcast0 = self.cpf_control0.check_update(t)
        if broadcast0 != -1:
            self.cpf_control1.reset(broadcast0)

        broadcast1 = self.cpf_control1.check_update(t)
        if broadcast1 != -1:
            self.cpf_control0.reset(broadcast1)


        _, outputs_cpf0 = self.cpf_control0.inputs_outputs()
        _, outputs_cpf1 = self.cpf_control1.inputs_outputs()



        # Connection of variables
        # First AUV
        inputs_kine0["u"] = outputs_pf0["u"]
        inputs_kine0["velocity"] = outputs_cpf0["velocity"]
        inputs_kine0["velocity_dot"] = outputs_cpf0["velocity_dot"]
        
        inputs_pf0["x"] = outputs_kine0["x"]
        inputs_pf0["y"] = outputs_kine0["y"]
        inputs_pf0["theta_m"] = outputs_kine0["theta_m"]
        inputs_pf0["velocity"] = outputs_cpf0["velocity"]
        inputs_pf0["velocity_dot"] = outputs_cpf0["velocity_dot"]

        self.cpf_control0.inputs["gamma0"] = outputs_pf0["s"]

        # Second AUV
        inputs_kine1["u"] = outputs_pf1["u"]
        inputs_kine1["velocity"] = outputs_cpf1["velocity"]
        inputs_kine1["velocity_dot"] = outputs_cpf1["velocity_dot"]
        
        inputs_pf1["x"] = outputs_kine1["x"]
        inputs_pf1["y"] = outputs_kine1["y"]
        inputs_pf1["theta_m"] = outputs_kine1["theta_m"]
        inputs_pf1["velocity"] = outputs_cpf1["velocity"]
        inputs_pf1["velocity_dot"] = outputs_cpf1["velocity_dot"]

        self.cpf_control1.inputs["gamma1"] = outputs_pf1["s"]


        outputs = {}
        outputs["x0"] = outputs_kine0["x"]
        outputs["y0"] = outputs_kine0["y"]
        outputs["theta_m0"] = outputs_kine0["theta_m"]
        outputs["x1"] = outputs_kine1["x"]
        outputs["y1"] = outputs_kine1["y"]
        outputs["theta_m1"] = outputs_kine1["theta_m"]
        outputs["s0"] = outputs_pf0["s"]
        outputs["u0"] = outputs_pf0["u"]
        outputs["s1"] = outputs_pf1["s"]
        outputs["u1"] = outputs_pf1["u"]
        outputs["velocity0"] = outputs_cpf0["velocity"]
        outputs["velocity_dot0"] = outputs_cpf0["velocity_dot"]
        outputs["velocity1"] = outputs_cpf1["velocity"]
        outputs["velocity_dot1"] = outputs_cpf1["velocity_dot"]
        outputs["gamma00"] = self.cpf_control0.state["gamma_hat0"]
        outputs["gamma01"] = self.cpf_control0.state["gamma_hat1"]
        outputs["gamma10"] = self.cpf_control1.state["gamma_hat0"]
        outputs["gamma11"] = self.cpf_control1.state["gamma_hat1"]

        # Save outputs for plotting
        if self.history:
            for key in self.past_outputs.keys():
                self.past_outputs[key].append(outputs[key])

        self.time.append(t)


        # Update the system
        self.kine0.auv_update(inputs_kine0, dt=self.dt)
        self.pf_control0.pf_update(inputs_pf0, dt=self.dt)
        self.cpf_control0.cpf_update(dt=self.dt)
        self.kine1.auv_update(inputs_kine1, dt=self.dt)
        self.pf_control1.pf_update(inputs_pf1, dt=self.dt)
        self.cpf_control1.cpf_update(dt=self.dt)

        return outputs

    def set_initial_conditions(self, init_cond):
        self.kine0.set_initial_conditions(init_cond["x0"], init_cond["y0"], init_cond["theta_m0"])
        self.pf_control0.set_initial_conditions(init_cond["s0"])

        self.kine1.set_initial_conditions(init_cond["x1"], init_cond["y1"], init_cond["theta_m1"])
        self.pf_control1.set_initial_conditions(init_cond["s1"])

        gammas = {"gamma0": init_cond["s0"], "gamma1": init_cond["s1"]}
        self.cpf_control0.set_initial_conditions(gammas)
        self.cpf_control1.set_initial_conditions(gammas)

    def past_values(self):
        return (self.past_outputs, self.kine0.past_state, self.pf_control0.past_state, self.cpf_control0.past_state, self.kine1.past_state, self.pf_control1.past_state, self.cpf_control1.past_state)







class DoubleAUVMPFETCTest:
    def __init__(self, path0, path1, pf_params=None, cpf_params=None, etc_type="Time", factor=10, history=False, dt=1):
        self.dt = dt
        self.factor = factor
        self.path0 = path0
        self.path1 = path1
        self.pf_prarams = pf_params
        self.cpf_params = cpf_params
        
        #self.inputs = {"velocity": 0, "velocity_dot": 0}
        self.time = []
        
        self.history = history
        if history:
            state_history = True
            self.past_outputs = {
                "x0": [],
                "y0": [],
                "theta_m0": [],
                "s0": [],
                "u0": [],
                "x1": [],
                "y1": [],
                "theta_m1": [],
                "s1": [],
                "u1": [],
                "velocity0": [],
                "velocity1": []
                }
        else:
            state_history = False

        A_matrix = np.array([[0, 1],[1, 0]])

        self.kine_target = kn.Kinematics(saturate=0, state_history=state_history, dt=dt)
        self.pf_control_target = pf.Lapierre(some_path=path0, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        #self.cpf_control_target = cpf.CPFContinuousController(num_auv=2, id=0, k_csi=cpf_params["k_csi0"], params=cpf_params, A_matrix=A_matrix, state_history=state_history, dt=dt)
        self.cpf_control_target = cpf.CPFDiscreteControllerETC(num_auv=2, id=0, params=cpf_params, k_csi=cpf_params["k_csi0"], A_matrix=A_matrix, etc_type=etc_type, state_history=state_history, dt=dt)

        self.mpf_control_follower = mpf.MovingPathFollowingTest(saturate=0, state_history=state_history, dt=dt)
        self.pf_control_follower = pf.Lapierre(some_path=path1, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        #self.cpf_control_follower = cpf.CPFContinuousController(num_auv=2, id=1, k_csi=cpf_params["k_csi1"], params=cpf_params, A_matrix=A_matrix, state_history=state_history, dt=dt)
        self.cpf_control_follower = cpf.CPFDiscreteControllerETC(num_auv=2, id=1, params=cpf_params, k_csi=cpf_params["k_csi1"], A_matrix=A_matrix, etc_type=etc_type, state_history=state_history, dt=dt)
        
    def update(self, t):
        
        # Get dictionaries setup
        inputs_kine_target, outputs_kine_target = self.kine_target.inputs_outputs()
        inputs_pf_target, outputs_pf_target = self.pf_control_target.inputs_outputs()
        inputs_cpf_target, outputs_cpf_target = self.cpf_control_target.inputs_outputs()

        inputs_mpf_follower, outputs_mpf_follower = self.mpf_control_follower.inputs_outputs()
        inputs_pf_follower, outputs_pf_follower = self.pf_control_follower.inputs_outputs()
        inputs_cpf_follower, outputs_cpf_follower = self.cpf_control_follower.inputs_outputs()



        self.cpf_control_target.inputs["gamma0"] = outputs_pf_target["s"]
        #self.cpf_control_target.inputs["gamma1"] = (outputs_pf_follower["s"] + self.pf_control_follower.laps) / self.factor

        #self.cpf_control_follower.inputs["gamma0"] = outputs_pf_target["s"]
        self.cpf_control_follower.inputs["gamma1"] = (outputs_pf_follower["s"] + self.pf_control_follower.laps) / self.factor



        
        # Check if comms needs update
        broadcast0 = self.cpf_control_target.check_update(t)
        if broadcast0 != -1:
            self.cpf_control_follower.reset(broadcast0)

        broadcast1 = self.cpf_control_follower.check_update(t)
        if broadcast1 != -1:
            self.cpf_control_target.reset(broadcast1)
        





        _, outputs_cpf_target = self.cpf_control_target.inputs_outputs()
        _, outputs_cpf_follower = self.cpf_control_follower.inputs_outputs()



        # Connection of variables
        # First AUV
        inputs_kine_target["u"] = outputs_pf_target["u"]
        inputs_kine_target["velocity"] = outputs_cpf_target["velocity"]
        inputs_kine_target["velocity_dot"] = outputs_cpf_target["velocity_dot"]
        
        inputs_pf_target["x"] = outputs_kine_target["x"]
        inputs_pf_target["y"] = outputs_kine_target["y"]
        inputs_pf_target["theta_m"] = outputs_kine_target["theta_m"]
        inputs_pf_target["velocity"] = outputs_cpf_target["velocity"]
        inputs_pf_target["velocity_dot"] = outputs_cpf_target["velocity_dot"]

        #self.cpf_control_target.inputs["gamma0"] = outputs_pf_target[""]
        self.cpf_control_target.inputs["gamma0"] = outputs_pf_target["s"]

        # Second AUV
        inputs_mpf_follower["target_x"] = self.path0.get_x(outputs_pf_target["s"])
        inputs_mpf_follower["target_y"] = self.path0.get_y(outputs_pf_target["s"])
        inputs_mpf_follower["target_yaw"] = self.path0.get_theta_c(outputs_pf_target["s"])
        inputs_mpf_follower["target_u"] = 0.017
        inputs_mpf_follower["target_velocity"] = self.cpf_params["speed_profile0"]
        inputs_mpf_follower["follower_u"] = outputs_pf_follower["u"]
        inputs_mpf_follower["follower_velocity"] = outputs_cpf_follower["velocity"]
        
        inputs_pf_follower["x"] = outputs_mpf_follower["x_ref"]
        inputs_pf_follower["y"] = outputs_mpf_follower["y_ref"]
        inputs_pf_follower["theta_m"] = outputs_mpf_follower["theta_m_ref"]
        inputs_pf_follower["velocity"] = outputs_cpf_follower["velocity"]
        inputs_pf_follower["velocity_dot"] = outputs_cpf_follower["velocity_dot"]

        self.cpf_control_follower.inputs["gamma1"] = (outputs_pf_follower["s"] + self.pf_control_follower.laps) / self.factor


        outputs = {}
        outputs["x0"] = outputs_kine_target["x"]
        outputs["y0"] = outputs_kine_target["y"]
        outputs["theta_m0"] = outputs_kine_target["theta_m"]
        outputs["x1"] = outputs_mpf_follower["x"]
        outputs["y1"] = outputs_mpf_follower["y"]
        outputs["theta_m1"] = outputs_mpf_follower["theta_m"]
        outputs["s0"] = outputs_pf_target["s"]
        outputs["u0"] = outputs_pf_target["u"]
        outputs["s1"] = outputs_pf_follower["s"]
        outputs["u1"] = outputs_pf_follower["u"]
        outputs["velocity0"] = outputs_cpf_target["velocity"]
        outputs["velocity1"] = outputs_cpf_follower["velocity"]

        # Save outputs for plotting
        if self.history:
            for key in self.past_outputs.keys():
                self.past_outputs[key].append(outputs[key])

        self.time.append(t)


        # Update the system
        self.kine_target.auv_update(inputs_kine_target, dt=self.dt)
        self.pf_control_target.pf_update(inputs_pf_target, dt=self.dt)
        self.cpf_control_target.cpf_update(dt=self.dt)
        self.mpf_control_follower.mpf_update(inputs_mpf_follower, dt=self.dt)
        self.pf_control_follower.pf_update(inputs_pf_follower, dt=self.dt)
        self.cpf_control_follower.cpf_update(dt=self.dt)

        return outputs

    def set_initial_conditions(self, init_cond):
        self.kine_target.set_initial_conditions(init_cond["x0"], init_cond["y0"], init_cond["theta_m0"])
        self.pf_control_target.set_initial_conditions(init_cond["s0"])

        #pir = self.mpf_control_follower.point_in_reference(init_cond["x1"], init_cond["y1"], init_cond["x0"], init_cond["y0"], init_cond["theta_m0"])
        ry = self.mpf_control_follower.reference_yaw(init_cond["theta_m1"], init_cond["theta_m0"])
        self.mpf_control_follower.set_initial_conditions(init_cond["x1"], init_cond["y1"], ry)
        self.pf_control_follower.set_initial_conditions(init_cond["s1"])

        gammas = {"gamma0": init_cond["s0"], "gamma1": init_cond["s1"]}
        self.cpf_control_target.set_initial_conditions(gammas)
        self.cpf_control_follower.set_initial_conditions(gammas)

    def past_values(self):
        return (self.past_outputs, self.kine_target.past_state, self.pf_control_target.past_state, self.cpf_control_target.past_state, self.mpf_control_follower.past_state, self.pf_control_follower.past_state, self.cpf_control_follower.past_state)











class DoubleAUVMPFETC:
    def __init__(self, path_target, path0, path1, pf_params=None, cpf_params=None, etc_type="Time", history=False, dt=1):
        self.dt = dt
        self.path_target = path_target
        self.path0 = path0
        self.path1 = path1
        self.pf_prarams = pf_params
        self.cpf_params = cpf_params
        
        #self.inputs = {"velocity": 0, "velocity_dot": 0}
        self.time = []
        
        self.history = history
        if history:
            state_history = True
            self.past_outputs = {
                "x_target": [],
                "y_target": [],
                "theta_m_target": [],
                "s_target": [],
                "u_target": [],
                "x0": [],
                "y0": [],
                "theta_m0": [],
                "s0": [],
                "u0": [],
                "x1": [],
                "y1": [],
                "theta_m1": [],
                "s1": [],
                "u1": [],
                "velocity0": [],
                "velocity1": []
            }
        else:
            state_history = False

        A_matrix = np.array([[0, 1],[1, 0]])

        self.kine_target = kn.Kinematics(saturate=0, state_history=state_history, dt=dt)
        self.pf_control_target = pf.Lapierre(some_path=path_target, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)

        self.mpf_control_follower0 = mpf.MovingPathFollowingTest(saturate=0, state_history=state_history, dt=dt)
        self.pf_control_follower0 = pf.Lapierre(some_path=path0, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        self.cpf_control_follower0 = cpf.CPFDiscreteControllerETC(num_auv=2, id=0, params=cpf_params, k_csi=cpf_params["k_csi0"], A_matrix=A_matrix, etc_type=etc_type, state_history=state_history, dt=dt)
        
        self.mpf_control_follower1 = mpf.MovingPathFollowingTest(saturate=0, state_history=state_history, dt=dt)
        self.pf_control_follower1 = pf.Lapierre(some_path=path1, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        self.cpf_control_follower1 = cpf.CPFDiscreteControllerETC(num_auv=2, id=1, params=cpf_params, k_csi=cpf_params["k_csi1"], A_matrix=A_matrix, etc_type=etc_type, state_history=state_history, dt=dt)

    def update(self, t):
        
        # Get dictionaries setup
        inputs_kine_target, outputs_kine_target = self.kine_target.inputs_outputs()
        inputs_pf_target, outputs_pf_target = self.pf_control_target.inputs_outputs()

        inputs_mpf_follower0, outputs_mpf_follower0 = self.mpf_control_follower0.inputs_outputs()
        inputs_pf_follower0, outputs_pf_follower0 = self.pf_control_follower0.inputs_outputs()
        inputs_cpf_follower0, outputs_cpf_follower0 = self.cpf_control_follower0.inputs_outputs()

        inputs_mpf_follower1, outputs_mpf_follower1 = self.mpf_control_follower1.inputs_outputs()
        inputs_pf_follower1, outputs_pf_follower1 = self.pf_control_follower1.inputs_outputs()
        inputs_cpf_follower1, outputs_cpf_follower1 = self.cpf_control_follower1.inputs_outputs()


        self.cpf_control_follower0.inputs["gamma0"] = outputs_pf_follower0["s"]
        self.cpf_control_follower1.inputs["gamma1"] = outputs_pf_follower1["s"]



        
        # Check if comms needs update
        broadcast0 = self.cpf_control_follower0.check_update(t)
        if broadcast0 != -1:
            self.cpf_control_follower1.reset(broadcast0)

        broadcast1 = self.cpf_control_follower1.check_update(t)
        if broadcast1 != -1:
            self.cpf_control_follower0.reset(broadcast1)
        





        _, outputs_cpf_follower0 = self.cpf_control_follower0.inputs_outputs()
        _, outputs_cpf_follower1 = self.cpf_control_follower1.inputs_outputs()



        # Connection of variables
        # Virtual Target AUV
        inputs_kine_target["u"] = outputs_pf_target["u"]
        inputs_kine_target["velocity"] = 0.25
        inputs_kine_target["velocity_dot"] = 0
        
        inputs_pf_target["x"] = outputs_kine_target["x"]
        inputs_pf_target["y"] = outputs_kine_target["y"]
        inputs_pf_target["theta_m"] = outputs_kine_target["theta_m"]
        inputs_pf_target["velocity"] = 0.25
        inputs_pf_target["velocity_dot"] = 0

        # First ASV
        inputs_mpf_follower0["target_x"] = outputs_kine_target["x"]
        inputs_mpf_follower0["target_y"] = outputs_kine_target["y"]
        inputs_mpf_follower0["target_yaw"] = outputs_kine_target["theta_m"]
        inputs_mpf_follower0["target_u"] = outputs_pf_target["u"]
        inputs_mpf_follower0["target_velocity"] = 0.25
        inputs_mpf_follower0["follower_u"] = outputs_pf_follower0["u"]
        inputs_mpf_follower0["follower_velocity"] = outputs_cpf_follower0["velocity"]
        
        inputs_pf_follower0["x"] = outputs_mpf_follower0["x_ref"]
        inputs_pf_follower0["y"] = outputs_mpf_follower0["y_ref"]
        inputs_pf_follower0["theta_m"] = outputs_mpf_follower0["theta_m_ref"]
        inputs_pf_follower0["velocity"] = outputs_cpf_follower0["velocity"]
        inputs_pf_follower0["velocity_dot"] = outputs_cpf_follower0["velocity_dot"]

        self.cpf_control_follower0.inputs["gamma0"] = outputs_pf_follower0["s"]

        # Second ASV
        inputs_mpf_follower1["target_x"] = outputs_kine_target["x"]
        inputs_mpf_follower1["target_y"] = outputs_kine_target["y"]
        inputs_mpf_follower1["target_yaw"] = outputs_kine_target["theta_m"]
        inputs_mpf_follower1["target_u"] = outputs_pf_target["u"]
        inputs_mpf_follower1["target_velocity"] = 0.25
        inputs_mpf_follower1["follower_u"] = outputs_pf_follower1["u"]
        inputs_mpf_follower1["follower_velocity"] = outputs_cpf_follower1["velocity"]
        
        inputs_pf_follower1["x"] = outputs_mpf_follower1["x_ref"]
        inputs_pf_follower1["y"] = outputs_mpf_follower1["y_ref"]
        inputs_pf_follower1["theta_m"] = outputs_mpf_follower1["theta_m_ref"]
        inputs_pf_follower1["velocity"] = outputs_cpf_follower1["velocity"]
        inputs_pf_follower1["velocity_dot"] = outputs_cpf_follower1["velocity_dot"]

        self.cpf_control_follower1.inputs["gamma1"] = outputs_pf_follower1["s"]


        outputs = {}
        outputs["x_target"] = outputs_kine_target["x"]
        outputs["y_target"] = outputs_kine_target["y"]
        outputs["theta_m_target"] = outputs_kine_target["theta_m"]
        outputs["s_target"] = outputs_pf_target["s"]
        outputs["u_target"] = outputs_pf_target["u"]
        outputs["x0"] = outputs_mpf_follower0["x"]
        outputs["y0"] = outputs_mpf_follower0["y"]
        outputs["theta_m0"] = outputs_mpf_follower0["theta_m"]
        outputs["s0"] = outputs_pf_follower0["s"]
        outputs["u0"] = outputs_pf_follower0["u"]
        outputs["x1"] = outputs_mpf_follower1["x"]
        outputs["y1"] = outputs_mpf_follower1["y"]
        outputs["theta_m1"] = outputs_mpf_follower1["theta_m"]
        outputs["s1"] = outputs_pf_follower1["s"]
        outputs["u1"] = outputs_pf_follower1["u"]
        outputs["velocity0"] = outputs_cpf_follower0["velocity"]
        outputs["velocity1"] = outputs_cpf_follower1["velocity"]

        # Save outputs for plotting
        if self.history:
            for key in self.past_outputs.keys():
                self.past_outputs[key].append(outputs[key])

        self.time.append(t)


        # Update the system
        self.kine_target.auv_update(inputs_kine_target, dt=self.dt)
        self.pf_control_target.pf_update(inputs_pf_target, dt=self.dt)
        self.mpf_control_follower0.mpf_update(inputs_mpf_follower0, dt=self.dt)
        self.pf_control_follower0.pf_update(inputs_pf_follower0, dt=self.dt)
        self.mpf_control_follower1.mpf_update(inputs_mpf_follower1, dt=self.dt)
        self.pf_control_follower1.pf_update(inputs_pf_follower1, dt=self.dt)
        self.cpf_control_follower0.cpf_update(dt=self.dt)
        self.cpf_control_follower1.cpf_update(dt=self.dt)

        return outputs

    def set_initial_conditions(self, init_cond):
        self.kine_target.set_initial_conditions(init_cond["x_target"], init_cond["y_target"], init_cond["theta_m_target"])
        self.pf_control_target.set_initial_conditions(init_cond["s_target"])

        #pir = self.mpf_control_follower.point_in_reference(init_cond["x1"], init_cond["y1"], init_cond["x0"], init_cond["y0"], init_cond["theta_m0"])
        ry = self.mpf_control_follower0.reference_yaw(init_cond["theta_m0"], init_cond["theta_m_target"])
        self.mpf_control_follower0.set_initial_conditions(init_cond["x0"], init_cond["y0"], ry)
        self.pf_control_follower0.set_initial_conditions(init_cond["s0"])

        ry = self.mpf_control_follower1.reference_yaw(init_cond["theta_m1"], init_cond["theta_m_target"])
        self.mpf_control_follower1.set_initial_conditions(init_cond["x1"], init_cond["y1"], ry)
        self.pf_control_follower1.set_initial_conditions(init_cond["s1"])

        gammas = {"gamma0": init_cond["s0"], "gamma1": init_cond["s1"]}
        self.cpf_control_follower0.set_initial_conditions(gammas)
        self.cpf_control_follower1.set_initial_conditions(gammas)

    def past_values(self):
        return (self.past_outputs, self.kine_target.past_state, self.pf_control_target.past_state, self.mpf_control_follower0.past_state, self.pf_control_follower0.past_state, self.cpf_control_follower0.past_state, self.mpf_control_follower1.past_state, self.pf_control_follower1.past_state, self.cpf_control_follower1.past_state)







class DoubleASVMPFETCOnTripleAUV:
    def __init__(self, path_target0, path_target1, path_target2, path_follower0, path_follower1, pf_params=None, cpf_params_target=None, cpf_params_follower=None, etc_type="Time", history=False, dt=1):
        self.dt = dt
        self.path_target0 = path_target0
        self.path_target1 = path_target1
        self.path_target2 = path_target2
        self.path_follower0 = path_follower0
        self.path_follower1 = path_follower1
        self.pf_prarams = pf_params
        self.cpf_params_target = cpf_params_target
        self.cpf_params_follower = cpf_params_follower
        
        self.time = []
        
        self.history = history
        if history:
            state_history = True
            self.past_outputs = {
                "x_target0": [],
                "y_target0": [],
                "theta_m_target0": [],
                "s_target0": [],
                "u_target0": [],
                "x_target1": [],
                "y_target1": [],
                "theta_m_target1": [],
                "s_target1": [],
                "u_target1": [],
                "x_target2": [],
                "y_target2": [],
                "theta_m_target2": [],
                "s_target2": [],
                "u_target2": [],
                "x_follower0": [],
                "y_follower0": [],
                "theta_m_follower0": [],
                "s_follower0": [],
                "u_follower0": [],
                "x_follower1": [],
                "y_follower1": [],
                "theta_m_follower1": [],
                "s_follower1": [],
                "u_follower1": [],
                "velocity_target0": [],
                "velocity_target1": [],
                "velocity_target2": [],
                "velocity_follower0": [],
                "velocity_follower1": []
            }
        else:
            state_history = False

        A_matrix_target = np.array([[0, 1, 1], [1, 0, 1], [1, 1, 0]])
        A_matrix_follower = np.array([[0, 1], [1, 0]])

        self.kine_target0 = kn.Kinematics(saturate=0, state_history=state_history, dt=dt)
        self.pf_control_target0 = pf.Lapierre(some_path=path_target0, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        self.cpf_control_target0 = cpf.CPFDiscreteControllerETC(num_auv=3, id=0, params=cpf_params_target, k_csi=cpf_params_target["k_csi0"], A_matrix=A_matrix_target, etc_type=etc_type, state_history=state_history, dt=dt)

        self.kine_target1 = kn.Kinematics(saturate=0, state_history=state_history, dt=dt)
        self.pf_control_target1 = pf.Lapierre(some_path=path_target1, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        self.cpf_control_target1 = cpf.CPFDiscreteControllerETC(num_auv=3, id=1, params=cpf_params_target, k_csi=cpf_params_target["k_csi1"], A_matrix=A_matrix_target, etc_type=etc_type, state_history=state_history, dt=dt)

        self.kine_target2 = kn.Kinematics(saturate=0, state_history=state_history, dt=dt)
        self.pf_control_target2 = pf.Lapierre(some_path=path_target2, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        self.cpf_control_target2 = cpf.CPFDiscreteControllerETC(num_auv=3, id=2, params=cpf_params_target, k_csi=cpf_params_target["k_csi2"], A_matrix=A_matrix_target, etc_type=etc_type, state_history=state_history, dt=dt)

        self.mpf_control_follower0 = mpf.MovingPathFollowingTest(saturate=0, state_history=state_history, dt=dt)
        self.pf_control_follower0 = pf.Lapierre(some_path=path_follower0, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        self.cpf_control_follower0 = cpf.CPFDiscreteControllerETC(num_auv=2, id=0, params=cpf_params_follower, k_csi=cpf_params_follower["k_csi0"], A_matrix=A_matrix_follower, etc_type=etc_type, state_history=state_history, dt=dt)
        
        self.mpf_control_follower1 = mpf.MovingPathFollowingTest(saturate=0, state_history=state_history, dt=dt)
        self.pf_control_follower1 = pf.Lapierre(some_path=path_follower1, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        self.cpf_control_follower1 = cpf.CPFDiscreteControllerETC(num_auv=2, id=1, params=cpf_params_follower, k_csi=cpf_params_follower["k_csi1"], A_matrix=A_matrix_follower, etc_type=etc_type, state_history=state_history, dt=dt)

    def update(self, t):
        # Get dictionaries setup
        inputs_kine_target0, outputs_kine_target0 = self.kine_target0.inputs_outputs()
        inputs_pf_target0, outputs_pf_target0 = self.pf_control_target0.inputs_outputs()
        inputs_cpf_target0, outputs_cpf_target0 = self.cpf_control_target0.inputs_outputs()

        inputs_kine_target1, outputs_kine_target1 = self.kine_target1.inputs_outputs()
        inputs_pf_target1, outputs_pf_target1 = self.pf_control_target1.inputs_outputs()
        inputs_cpf_target1, outputs_cpf_target1 = self.cpf_control_target1.inputs_outputs()

        inputs_kine_target2, outputs_kine_target2 = self.kine_target2.inputs_outputs()
        inputs_pf_target2, outputs_pf_target2 = self.pf_control_target2.inputs_outputs()
        inputs_cpf_target2, outputs_cpf_target2 = self.cpf_control_target2.inputs_outputs()

        inputs_mpf_follower0, outputs_mpf_follower0 = self.mpf_control_follower0.inputs_outputs()
        inputs_pf_follower0, outputs_pf_follower0 = self.pf_control_follower0.inputs_outputs()
        inputs_cpf_follower0, outputs_cpf_follower0 = self.cpf_control_follower0.inputs_outputs()

        inputs_mpf_follower1, outputs_mpf_follower1 = self.mpf_control_follower1.inputs_outputs()
        inputs_pf_follower1, outputs_pf_follower1 = self.pf_control_follower1.inputs_outputs()
        inputs_cpf_follower1, outputs_cpf_follower1 = self.cpf_control_follower1.inputs_outputs()


        self.cpf_control_target0.inputs["gamma0"] = outputs_pf_target0["s"]
        self.cpf_control_target1.inputs["gamma1"] = outputs_pf_target1["s"]
        self.cpf_control_target2.inputs["gamma2"] = outputs_pf_target2["s"]

        self.cpf_control_follower0.inputs["gamma0"] = outputs_pf_follower0["s"]
        self.cpf_control_follower1.inputs["gamma1"] = outputs_pf_follower1["s"]



        
        # Check if comms needs update
        broadcast_target0 = self.cpf_control_target0.check_update(t)
        if broadcast_target0 != -1:
            self.cpf_control_target1.reset(broadcast_target0)
            self.cpf_control_target2.reset(broadcast_target0)

        broadcast_target1 = self.cpf_control_target1.check_update(t)
        if broadcast_target1 != -1:
            self.cpf_control_target0.reset(broadcast_target1)
            self.cpf_control_target2.reset(broadcast_target1)

        broadcast_target2 = self.cpf_control_target2.check_update(t)
        if broadcast_target2 != -1:
            self.cpf_control_target0.reset(broadcast_target2)
            self.cpf_control_target1.reset(broadcast_target2)


        broadcast_follower0 = self.cpf_control_follower0.check_update(t)
        if broadcast_follower0 != -1:
            self.cpf_control_follower1.reset(broadcast_follower0)

        broadcast_follower1 = self.cpf_control_follower1.check_update(t)
        if broadcast_follower1 != -1:
            self.cpf_control_follower0.reset(broadcast_follower1)
        



        _, outputs_cpf_target0 = self.cpf_control_target0.inputs_outputs()
        _, outputs_cpf_target1 = self.cpf_control_target1.inputs_outputs()
        _, outputs_cpf_target2 = self.cpf_control_target2.inputs_outputs()

        _, outputs_cpf_follower0 = self.cpf_control_follower0.inputs_outputs()
        _, outputs_cpf_follower1 = self.cpf_control_follower1.inputs_outputs()



        # Connection of variables
        # AUV Target 0
        inputs_kine_target0["u"] = outputs_pf_target0["u"]
        inputs_kine_target0["velocity"] = outputs_cpf_target0["velocity"]
        inputs_kine_target0["velocity_dot"] = outputs_cpf_target0["velocity_dot"]
        
        inputs_pf_target0["x"] = outputs_kine_target0["x"]
        inputs_pf_target0["y"] = outputs_kine_target0["y"]
        inputs_pf_target0["theta_m"] = outputs_kine_target0["theta_m"]
        inputs_pf_target0["velocity"] = outputs_cpf_target0["velocity"]
        inputs_pf_target0["velocity_dot"] = outputs_cpf_target0["velocity_dot"]

        self.cpf_control_target0.inputs["gamma0"] = outputs_pf_target0["s"]

        # AUV Target 1
        inputs_kine_target1["u"] = outputs_pf_target1["u"]
        inputs_kine_target1["velocity"] = outputs_cpf_target1["velocity"]
        inputs_kine_target1["velocity_dot"] = outputs_cpf_target1["velocity_dot"]
        
        inputs_pf_target1["x"] = outputs_kine_target1["x"]
        inputs_pf_target1["y"] = outputs_kine_target1["y"]
        inputs_pf_target1["theta_m"] = outputs_kine_target1["theta_m"]
        inputs_pf_target1["velocity"] = outputs_cpf_target1["velocity"]
        inputs_pf_target1["velocity_dot"] = outputs_cpf_target1["velocity_dot"]

        self.cpf_control_target1.inputs["gamma1"] = outputs_pf_target1["s"]

        # AUV Target 2
        inputs_kine_target2["u"] = outputs_pf_target2["u"]
        inputs_kine_target2["velocity"] = outputs_cpf_target2["velocity"]
        inputs_kine_target2["velocity_dot"] = outputs_cpf_target2["velocity_dot"]
        
        inputs_pf_target2["x"] = outputs_kine_target2["x"]
        inputs_pf_target2["y"] = outputs_kine_target2["y"]
        inputs_pf_target2["theta_m"] = outputs_kine_target2["theta_m"]
        inputs_pf_target2["velocity"] = outputs_cpf_target2["velocity"]
        inputs_pf_target2["velocity_dot"] = outputs_cpf_target2["velocity_dot"]

        self.cpf_control_target2.inputs["gamma2"] = outputs_pf_target2["s"]

        # First ASV
        inputs_mpf_follower0["target_x"] = self.path_target1.get_x(outputs_pf_target1["s"])
        inputs_mpf_follower0["target_y"] = self.path_target1.get_y(outputs_pf_target1["s"])
        inputs_mpf_follower0["target_yaw"] = self.path_target1.get_theta_c(outputs_pf_target1["s"])
        inputs_mpf_follower0["target_u"] = 2 * pi / (self.path_target1.total_distance / self.cpf_params_target["speed_profile1"])
        inputs_mpf_follower0["target_velocity"] = self.cpf_params_target["speed_profile1"]
        inputs_mpf_follower0["follower_u"] = outputs_pf_follower0["u"] #pi * np.tanh(outputs_pf_follower0["u"])
        inputs_mpf_follower0["follower_velocity"] = outputs_cpf_follower0["velocity"]
        
        inputs_pf_follower0["x"] = outputs_mpf_follower0["x_ref"]
        inputs_pf_follower0["y"] = outputs_mpf_follower0["y_ref"]
        inputs_pf_follower0["theta_m"] = outputs_mpf_follower0["theta_m_ref"]
        inputs_pf_follower0["velocity"] = outputs_cpf_follower0["velocity"]
        inputs_pf_follower0["velocity_dot"] = outputs_cpf_follower0["velocity_dot"]

        self.cpf_control_follower0.inputs["gamma0"] = outputs_pf_follower0["s"]

        # Second ASV
        inputs_mpf_follower1["target_x"] = self.path_target1.get_x(outputs_pf_target1["s"])
        inputs_mpf_follower1["target_y"] = self.path_target1.get_y(outputs_pf_target1["s"])
        inputs_mpf_follower1["target_yaw"] = self.path_target1.get_theta_c(outputs_pf_target1["s"])
        inputs_mpf_follower1["target_u"] = 2 * pi / (self.path_target1.total_distance / self.cpf_params_target["speed_profile1"])
        inputs_mpf_follower1["target_velocity"] = self.cpf_params_target["speed_profile1"]
        inputs_mpf_follower1["follower_u"] = outputs_pf_follower1["u"] #pi * np.tanh(outputs_pf_follower1["u"])
        inputs_mpf_follower1["follower_velocity"] = outputs_cpf_follower1["velocity"]
        
        inputs_pf_follower1["x"] = outputs_mpf_follower1["x_ref"]
        inputs_pf_follower1["y"] = outputs_mpf_follower1["y_ref"]
        inputs_pf_follower1["theta_m"] = outputs_mpf_follower1["theta_m_ref"]
        inputs_pf_follower1["velocity"] = outputs_cpf_follower1["velocity"]
        inputs_pf_follower1["velocity_dot"] = outputs_cpf_follower1["velocity_dot"]

        self.cpf_control_follower1.inputs["gamma1"] = outputs_pf_follower1["s"]


        #print("u = " + str(outputs_pf_target1["u"]))
        #print("calc =" + str(2 * pi / (self.path_target1.total_distance / self.cpf_params_target["speed_profile1"])))


        outputs = {}
        outputs["x_target0"] = outputs_kine_target0["x"]
        outputs["y_target0"] = outputs_kine_target0["y"]
        outputs["theta_m_target0"] = outputs_kine_target0["theta_m"]
        outputs["s_target0"] = outputs_pf_target0["s"]
        outputs["u_target0"] = outputs_pf_target0["u"]
        outputs["x_target1"] = outputs_kine_target1["x"]
        outputs["y_target1"] = outputs_kine_target1["y"]
        outputs["theta_m_target1"] = outputs_kine_target1["theta_m"]
        outputs["s_target1"] = outputs_pf_target1["s"]
        outputs["u_target1"] = outputs_pf_target1["u"]
        outputs["x_target2"] = outputs_kine_target2["x"]
        outputs["y_target2"] = outputs_kine_target2["y"]
        outputs["theta_m_target2"] = outputs_kine_target2["theta_m"]
        outputs["s_target2"] = outputs_pf_target2["s"]
        outputs["u_target2"] = outputs_pf_target2["u"]
        outputs["x_follower0"] = outputs_mpf_follower0["x"]
        outputs["y_follower0"] = outputs_mpf_follower0["y"]
        outputs["theta_m_follower0"] = outputs_mpf_follower0["theta_m"]
        outputs["s_follower0"] = outputs_pf_follower0["s"]
        outputs["u_follower0"] = outputs_pf_follower0["u"]
        outputs["x_follower1"] = outputs_mpf_follower1["x"]
        outputs["y_follower1"] = outputs_mpf_follower1["y"]
        outputs["theta_m_follower1"] = outputs_mpf_follower1["theta_m"]
        outputs["s_follower1"] = outputs_pf_follower1["s"]
        outputs["u_follower1"] = outputs_pf_follower1["u"]
        outputs["velocity_target0"] = outputs_cpf_target0["velocity"]
        outputs["velocity_target1"] = outputs_cpf_target1["velocity"]
        outputs["velocity_target2"] = outputs_cpf_target2["velocity"]
        outputs["velocity_follower0"] = outputs_cpf_follower0["velocity"]
        outputs["velocity_follower1"] = outputs_cpf_follower1["velocity"]

        # Save outputs for plotting
        if self.history:
            for key in self.past_outputs.keys():
                self.past_outputs[key].append(outputs[key])

        self.time.append(t)


        # Update the system
        self.kine_target0.auv_update(inputs_kine_target0, dt=self.dt)
        self.pf_control_target0.pf_update(inputs_pf_target0, dt=self.dt)
        self.cpf_control_target0.cpf_update(dt=self.dt)

        self.kine_target1.auv_update(inputs_kine_target1, dt=self.dt)
        self.pf_control_target1.pf_update(inputs_pf_target1, dt=self.dt)
        self.cpf_control_target1.cpf_update(dt=self.dt)

        self.kine_target2.auv_update(inputs_kine_target2, dt=self.dt)
        self.pf_control_target2.pf_update(inputs_pf_target2, dt=self.dt)
        self.cpf_control_target2.cpf_update(dt=self.dt)

        self.mpf_control_follower0.mpf_update(inputs_mpf_follower0, dt=self.dt)
        self.pf_control_follower0.pf_update(inputs_pf_follower0, dt=self.dt)
        self.cpf_control_follower0.cpf_update(dt=self.dt)

        self.mpf_control_follower1.mpf_update(inputs_mpf_follower1, dt=self.dt)
        self.pf_control_follower1.pf_update(inputs_pf_follower1, dt=self.dt)
        self.cpf_control_follower1.cpf_update(dt=self.dt)

        return outputs

    def set_initial_conditions(self, init_cond):
        gammas_target = {"gamma0": init_cond["s_target0"], "gamma1": init_cond["s_target1"], "gamma2": init_cond["s_target2"]}

        self.kine_target0.set_initial_conditions(init_cond["x_target0"], init_cond["y_target0"], init_cond["theta_m_target0"])
        self.pf_control_target0.set_initial_conditions(init_cond["s_target0"])
        self.cpf_control_target0.set_initial_conditions(gammas_target)

        self.kine_target1.set_initial_conditions(init_cond["x_target1"], init_cond["y_target1"], init_cond["theta_m_target1"])
        self.pf_control_target1.set_initial_conditions(init_cond["s_target1"])
        self.cpf_control_target1.set_initial_conditions(gammas_target)

        self.kine_target2.set_initial_conditions(init_cond["x_target2"], init_cond["y_target2"], init_cond["theta_m_target2"])
        self.pf_control_target2.set_initial_conditions(init_cond["s_target2"])
        self.cpf_control_target2.set_initial_conditions(gammas_target)

        ry = self.mpf_control_follower0.reference_yaw(init_cond["theta_m_follower0"], init_cond["theta_m_target1"])
        self.mpf_control_follower0.set_initial_conditions(init_cond["x_follower0"], init_cond["y_follower0"], ry)
        self.pf_control_follower0.set_initial_conditions(init_cond["s_follower0"])

        ry = self.mpf_control_follower1.reference_yaw(init_cond["theta_m_follower1"], init_cond["theta_m_target1"])
        self.mpf_control_follower1.set_initial_conditions(init_cond["x_follower1"], init_cond["y_follower1"], ry)
        self.pf_control_follower1.set_initial_conditions(init_cond["s_follower1"])

        gammas_follower = {"gamma0": init_cond["s_follower0"], "gamma1": init_cond["s_follower1"]}
        self.cpf_control_follower0.set_initial_conditions(gammas_follower)
        self.cpf_control_follower1.set_initial_conditions(gammas_follower)

    def past_values(self):
        return (
            self.past_outputs,
            self.kine_target0.past_state,
            self.pf_control_target0.past_state,
            self.cpf_control_target0.past_state,
            self.kine_target1.past_state,
            self.pf_control_target1.past_state,
            self.cpf_control_target1.past_state,
            self.kine_target2.past_state,
            self.pf_control_target2.past_state,
            self.cpf_control_target2.past_state,
            self.mpf_control_follower0.past_state,
            self.pf_control_follower0.past_state,
            self.cpf_control_follower0.past_state,
            self.mpf_control_follower1.past_state,
            self.pf_control_follower1.past_state,
            self.cpf_control_follower1.past_state
        )



















class ASVMPFOnAUVTargetPursuit:
    def __init__(self, path_target, path_tracker, pf_params=None, ekf_params=None, time_halted=50, history=False, dt=1):
        self.dt = dt
        self.path_target = path_target
        self.path_tracker = path_tracker
        self.pf_prarams = pf_params
        self.ekf_params = ekf_params
        self.time_halted = time_halted

        self.time = []
        
        self.history = history
        if history:
            state_history = True
            self.past_outputs = {
                "x_target": [],
                "y_target": [],
                "theta_m_target": [],
                "s_target": [],
                "u_target": [],
                "x_tracker": [],
                "y_tracker": [],
                "theta_m_tracker": [],
                "s_tracker": [],
                "u_tracker": [],
                "velocity_target": [],
                "velocity_tracker": [],
                "x_ekf": [],
                "y_ekf": [],
                "theta_ekf": [],
                "velocity_ekf": [],
                "theta_dot_ekf": [],
                "range": []
            }
        else:
            state_history = False


        self.kine_target = kn.Kinematics(saturate=0, state_history=state_history, dt=dt)
        self.pf_control_target = pf.Lapierre(some_path=path_target, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        
        self.mpf_control_tracker = mpf.MovingPathFollowingTest(target_velocity="Multiple", saturate=0, state_history=state_history, dt=dt)
        self.pf_control_tracker = pf.Lapierre(some_path=path_tracker, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        self.ekf_tracker = ekf.ExtendedKalmanFilter(F_matrix=ekf_params["F_matrix"], Q_matrix=ekf_params["Q_matrix"], R_matrix=ekf_params["R_matrix"], dt=dt)
        self.rms_tracker = ekf.RangeMeasureSimulation(R=ekf_params["R_matrix"], sampling_period=2)

    def update(self, t):
        # Get dictionaries setup
        inputs_kine_target, outputs_kine_target = self.kine_target.inputs_outputs()
        inputs_pf_target, outputs_pf_target = self.pf_control_target.inputs_outputs()

        inputs_mpf_tracker, outputs_mpf_tracker = self.mpf_control_tracker.inputs_outputs()
        inputs_pf_tracker, outputs_pf_tracker = self.pf_control_tracker.inputs_outputs()
        inputs_ekf_tracker, outputs_ekf_tracker = self.ekf_tracker.inputs_outputs()


        # EKF Prediction and Update
        inputs_ekf_tracker["tracker_x0"] = outputs_mpf_tracker["x"]
        inputs_ekf_tracker["tracker_y0"] = outputs_mpf_tracker["y"]
        tracker_pos = np.array([outputs_mpf_tracker["x"], outputs_mpf_tracker["y"]])
        target_pos = np.array([outputs_kine_target["x"], outputs_kine_target["y"]])
        y_k = self.rms_tracker.measurement(t, tracker_pos, target_pos)
        if t < 150 or t > 200:
            inputs_ekf_tracker["range0"] = y_k
        else:
            inputs_ekf_tracker["range0"] = None

        self.ekf_tracker.ekf_update(inputs_ekf_tracker, t)
        inputs_ekf_tracker, outputs_ekf_tracker = self.ekf_tracker.inputs_outputs()


        # Connection of variables
        # AUV Target
        inputs_kine_target["u"] = outputs_pf_target["u"]
        if t < self.time_halted:
            inputs_kine_target["velocity"] = 0.0
            inputs_pf_target["velocity"] = 0.0
        else:
            inputs_kine_target["velocity"] = 0.2
            inputs_pf_target["velocity"] = 0.2
        inputs_kine_target["velocity_dot"] = 0
        
        inputs_pf_target["x"] = outputs_kine_target["x"]
        inputs_pf_target["y"] = outputs_kine_target["y"]
        inputs_pf_target["theta_m"] = outputs_kine_target["theta_m"]
        
        inputs_pf_target["velocity_dot"] = 0


        # ASV
        if t < self.time_halted:
            inputs_mpf_tracker["target_x"] = -4.
            inputs_mpf_tracker["target_y"] = -10.
            inputs_mpf_tracker["target_x_dot"] = 0.
            inputs_mpf_tracker["target_y_dot"] = 0.
        else:
            inputs_mpf_tracker["target_x"] = outputs_ekf_tracker["x"]
            inputs_mpf_tracker["target_y"] = outputs_ekf_tracker["y"]
            inputs_mpf_tracker["target_x_dot"] = outputs_ekf_tracker["x_dot"]
            inputs_mpf_tracker["target_y_dot"] = outputs_ekf_tracker["y_dot"]
        
        #inputs_mpf_tracker["target_x"] = outputs_ekf_tracker["x"]
        #inputs_mpf_tracker["target_y"] = outputs_ekf_tracker["y"]
        #inputs_mpf_tracker["target_x_dot"] = outputs_ekf_tracker["x_dot"]
        #inputs_mpf_tracker["target_y_dot"] = outputs_ekf_tracker["y_dot"]
        inputs_mpf_tracker["target_yaw"] = 0#outputs_ekf_tracker["theta"]
        inputs_mpf_tracker["target_u"] = 0#outputs_ekf_tracker["theta_dot"]
        #inputs_mpf_tracker["target_velocity"] = 0
        
        inputs_mpf_tracker["follower_u"] = outputs_pf_tracker["u"]
        inputs_mpf_tracker["follower_velocity"] = 0.75
        
        inputs_pf_tracker["x"] = outputs_mpf_tracker["x_ref"]
        inputs_pf_tracker["y"] = outputs_mpf_tracker["y_ref"]
        inputs_pf_tracker["theta_m"] = outputs_mpf_tracker["theta_m_ref"]
        inputs_pf_tracker["velocity"] = 0.75
        inputs_pf_tracker["velocity_dot"] = 0



        outputs = {}
        outputs["x_target"] = outputs_kine_target["x"]
        outputs["y_target"] = outputs_kine_target["y"]
        outputs["theta_m_target"] = outputs_kine_target["theta_m"]
        outputs["s_target"] = outputs_pf_target["s"]
        outputs["u_target"] = outputs_pf_target["u"]
        outputs["x_tracker"] = outputs_mpf_tracker["x"]
        outputs["y_tracker"] = outputs_mpf_tracker["y"]
        outputs["theta_m_tracker"] = outputs_mpf_tracker["theta_m"]
        outputs["s_tracker"] = outputs_pf_tracker["s"]
        outputs["u_tracker"] = outputs_pf_tracker["u"]
        if t < self.time_halted:
            outputs["velocity_target"] = 0
        else:
            outputs["velocity_target"] = 0.2
        outputs["velocity_tracker"] = outputs_mpf_tracker["velocity"]
        outputs["x_ekf"] = outputs_ekf_tracker["x"]
        outputs["y_ekf"] = outputs_ekf_tracker["y"]
        outputs["theta_ekf"] = outputs_ekf_tracker["theta"]
        #print(np.power(outputs_ekf_tracker["x_dot"], 2))
        outputs["velocity_ekf"] = np.sqrt(np.power(outputs_ekf_tracker["x_dot"], 2) + np.power(outputs_ekf_tracker["y_dot"], 2))
        outputs["theta_dot_ekf"] = outputs_ekf_tracker["theta_dot"]
        outputs["range"] = y_k

        # Save outputs for plotting
        if self.history:
            for key in self.past_outputs.keys():
                self.past_outputs[key].append(outputs[key])

        self.time.append(t)


        # Update the system
        self.kine_target.auv_update(inputs_kine_target, dt=self.dt)
        self.pf_control_target.pf_update(inputs_pf_target, dt=self.dt)

        self.mpf_control_tracker.mpf_update(inputs_mpf_tracker, dt=self.dt)
        self.pf_control_tracker.pf_update(inputs_pf_tracker, dt=self.dt)

        return outputs

    def set_initial_conditions(self, init_cond):
        self.kine_target.set_initial_conditions(init_cond["x_target"], init_cond["y_target"], init_cond["theta_m_target"])
        self.pf_control_target.set_initial_conditions(init_cond["s_target"])

        ry = self.mpf_control_tracker.reference_yaw(init_cond["theta_m_follower"], init_cond["theta_m_target"])
        self.mpf_control_tracker.set_initial_conditions(init_cond["x_follower"], init_cond["y_follower"], ry)
        self.pf_control_tracker.set_initial_conditions(init_cond["s_follower"])
        ic_ekf = {
            "x": init_cond["x_target"],
            "y": init_cond["y_target"],
            "x_dot": 0,
            "y_dot": 0
        }
        self.ekf_tracker.set_initial_conditions(ic_ekf)

    def past_values(self):
        return (
            self.past_outputs,
            self.kine_target.past_state,
            self.pf_control_target.past_state,
            self.mpf_control_tracker.past_state,
            self.pf_control_tracker.past_state,
            self.ekf_tracker.past_state
        )










class DoubleASVMPFOnAUVTargetPursuit:
    def __init__(self, path_target0, path_target1, path_target2, path_tracker0, path_tracker1, pf_params=None, cpf_params_target=None, cpf_params_tracker=None, ekf_params=None, time_halted=50, etc_type="Time", history=False, dt=1):
        self.dt = dt
        self.path_target0 = path_target0
        self.path_target1 = path_target1
        self.path_target2 = path_target2
        self.path_tracker0 = path_tracker0
        self.path_tracker1 = path_tracker1
        self.pf_prarams = pf_params
        self.cpf_params_target = cpf_params_target
        self.cpf_params_tracker = cpf_params_tracker
        self.ekf_params = ekf_params
        self.time_halted = time_halted

        self.time = []
        
        self.history = history
        if history:
            state_history = True
            self.past_outputs = {
                "x_target0": [],
                "y_target0": [],
                "theta_m_target0": [],
                "s_target0": [],
                "u_target0": [],
                "x_target1": [],
                "y_target1": [],
                "theta_m_target1": [],
                "s_target1": [],
                "u_target1": [],
                "x_target2": [],
                "y_target2": [],
                "theta_m_target2": [],
                "s_target2": [],
                "u_target2": [],
                "x_tracker0": [],
                "y_tracker0": [],
                "theta_m_tracker0": [],
                "s_tracker0": [],
                "u_tracker0": [],
                "x_tracker1": [],
                "y_tracker1": [],
                "theta_m_tracker1": [],
                "s_tracker1": [],
                "u_tracker1": [],
                "velocity_target0": [],
                "velocity_target1": [],
                "velocity_target2": [],
                "velocity_tracker0": [],
                "velocity_tracker1": [],
                "x_ekf": [],
                "y_ekf": [],
                "theta_ekf": [],
                "velocity_ekf": [],
                "theta_dot_ekf": [],
                "range0": [],
                "range1": []
            }
        else:
            state_history = False


        self.A_matrix_target = np.array([[0, 1, 1], [1, 0, 1], [1, 1, 0]])
        self.A_matrix_tracker = np.array([[0, 1], [1, 0]])


        self.kine_target0 = kn.Kinematics(saturate=0, state_history=state_history, dt=dt)
        self.pf_control_target0 = pf.Lapierre(some_path=path_target0, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        self.cpf_control_target0 = cpf.CPFDiscreteControllerETC(num_auv=3, id=0, params=cpf_params_target, k_csi=cpf_params_target["k_csi0"], A_matrix=self.A_matrix_target, etc_type=etc_type, state_history=state_history, dt=dt)

        self.kine_target1 = kn.Kinematics(saturate=0, state_history=state_history, dt=dt)
        self.pf_control_target1 = pf.Lapierre(some_path=path_target1, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        self.cpf_control_target1 = cpf.CPFDiscreteControllerETC(num_auv=3, id=1, params=cpf_params_target, k_csi=cpf_params_target["k_csi1"], A_matrix=self.A_matrix_target, etc_type=etc_type, state_history=state_history, dt=dt)

        self.kine_target2 = kn.Kinematics(saturate=0, state_history=state_history, dt=dt)
        self.pf_control_target2 = pf.Lapierre(some_path=path_target2, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        self.cpf_control_target2 = cpf.CPFDiscreteControllerETC(num_auv=3, id=2, params=cpf_params_target, k_csi=cpf_params_target["k_csi2"], A_matrix=self.A_matrix_target, etc_type=etc_type, state_history=state_history, dt=dt)

        
        self.mpf_control_tracker0 = mpf.MovingPathFollowingTest(target_velocity="Multiple", saturate=0, state_history=state_history, dt=dt)
        self.pf_control_tracker0 = pf.Lapierre(some_path=path_tracker0, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        self.cpf_control_tracker0 = cpf.CPFDiscreteControllerETC(num_auv=2, id=0, params=cpf_params_tracker, k_csi=cpf_params_tracker["k_csi0"], A_matrix=self.A_matrix_tracker, etc_type="Time", state_history=state_history, dt=dt)
        self.rms_tracker0 = ekf.RangeMeasureSimulation(R=ekf_params["R_matrix"][0][0], sampling_period=2)
        self.ekf_tracker = ekf.ExtendedKalmanFilter(F_matrix=ekf_params["F_matrix"], Q_matrix=ekf_params["Q_matrix"], R_matrix=ekf_params["R_matrix"], dt=dt)
        
        self.mpf_control_tracker1 = mpf.MovingPathFollowingTest(target_velocity="Multiple", saturate=0, state_history=state_history, dt=dt)
        self.pf_control_tracker1 = pf.Lapierre(some_path=path_tracker1, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        self.cpf_control_tracker1 = cpf.CPFDiscreteControllerETC(num_auv=2, id=1, params=cpf_params_tracker, k_csi=cpf_params_tracker["k_csi1"], A_matrix=self.A_matrix_tracker, etc_type="Time", state_history=state_history, dt=dt)
        self.rms_tracker1 = ekf.RangeMeasureSimulation(R=ekf_params["R_matrix"][1][1], sampling_period=2)

    def update(self, t):
        # Get dictionaries setup
        inputs_kine_target0, outputs_kine_target0 = self.kine_target0.inputs_outputs()
        inputs_pf_target0, outputs_pf_target0 = self.pf_control_target0.inputs_outputs()
        inputs_cpf_target0, outputs_cpf_target0 = self.cpf_control_target0.inputs_outputs()

        inputs_kine_target1, outputs_kine_target1 = self.kine_target1.inputs_outputs()
        inputs_pf_target1, outputs_pf_target1 = self.pf_control_target1.inputs_outputs()
        inputs_cpf_target1, outputs_cpf_target1 = self.cpf_control_target1.inputs_outputs()

        inputs_kine_target2, outputs_kine_target2 = self.kine_target2.inputs_outputs()
        inputs_pf_target2, outputs_pf_target2 = self.pf_control_target2.inputs_outputs()
        inputs_cpf_target2, outputs_cpf_target2 = self.cpf_control_target2.inputs_outputs()


        inputs_mpf_tracker0, outputs_mpf_tracker0 = self.mpf_control_tracker0.inputs_outputs()
        inputs_pf_tracker0, outputs_pf_tracker0 = self.pf_control_tracker0.inputs_outputs()
        inputs_cpf_tracker0, outputs_cpf_tracker0 = self.cpf_control_tracker0.inputs_outputs()
        inputs_ekf_tracker, outputs_ekf_tracker = self.ekf_tracker.inputs_outputs()

        inputs_mpf_tracker1, outputs_mpf_tracker1 = self.mpf_control_tracker1.inputs_outputs()
        inputs_pf_tracker1, outputs_pf_tracker1 = self.pf_control_tracker1.inputs_outputs()
        inputs_cpf_tracker1, outputs_cpf_tracker1 = self.cpf_control_tracker1.inputs_outputs()


        self.cpf_control_target0.inputs["gamma0"] = outputs_pf_target0["s"]
        self.cpf_control_target1.inputs["gamma1"] = outputs_pf_target1["s"]
        self.cpf_control_target2.inputs["gamma2"] = outputs_pf_target2["s"]

        self.cpf_control_tracker0.inputs["gamma0"] = outputs_pf_tracker0["s"]
        self.cpf_control_tracker1.inputs["gamma1"] = outputs_pf_tracker1["s"]


        # EKF Prediction and Update
        inputs_ekf_tracker["tracker_x0"] = outputs_mpf_tracker0["x"]
        inputs_ekf_tracker["tracker_y0"] = outputs_mpf_tracker0["y"]
        inputs_ekf_tracker["tracker_x1"] = outputs_mpf_tracker1["x"]
        inputs_ekf_tracker["tracker_y1"] = outputs_mpf_tracker1["y"]
        tracker0_pos = np.array([outputs_mpf_tracker0["x"], outputs_mpf_tracker0["y"]])
        tracker1_pos = np.array([outputs_mpf_tracker1["x"], outputs_mpf_tracker1["y"]])
        target_pos = np.array([outputs_kine_target1["x"], outputs_kine_target1["y"]])
        y_k0 = self.rms_tracker0.measurement(t, tracker0_pos, target_pos)
        y_k1 = self.rms_tracker1.measurement(t, tracker1_pos, target_pos)
        if t < 150 or t > 200:
            inputs_ekf_tracker["range0"] = y_k0
            inputs_ekf_tracker["range1"] = y_k1
        else:
            inputs_ekf_tracker["range0"] = None
            inputs_ekf_tracker["range1"] = None

        self.ekf_tracker.ekf_update(inputs_ekf_tracker, t)
        inputs_ekf_tracker, outputs_ekf_tracker = self.ekf_tracker.inputs_outputs()


        # CPF ETC update
        broadcast_target0 = self.cpf_control_target0.check_update(t)
        if broadcast_target0 != -1:
            self.cpf_control_target1.reset(broadcast_target0)
            self.cpf_control_target2.reset(broadcast_target0)

        broadcast_target1 = self.cpf_control_target1.check_update(t)
        if broadcast_target1 != -1:
            self.cpf_control_target0.reset(broadcast_target1)
            self.cpf_control_target2.reset(broadcast_target1)

        broadcast_target2 = self.cpf_control_target2.check_update(t)
        if broadcast_target2 != -1:
            self.cpf_control_target0.reset(broadcast_target2)
            self.cpf_control_target1.reset(broadcast_target2)
        
        _, outputs_cpf_target0 = self.cpf_control_target0.inputs_outputs()
        _, outputs_cpf_target1 = self.cpf_control_target1.inputs_outputs()
        _, outputs_cpf_target2 = self.cpf_control_target2.inputs_outputs()


        broadcast_tracker0 = self.cpf_control_tracker0.check_update(t)
        if broadcast_tracker0 != -1:
            self.cpf_control_tracker1.reset(broadcast_tracker0)

        broadcast_tracker1 = self.cpf_control_tracker1.check_update(t)
        if broadcast_tracker1 != -1:
            self.cpf_control_tracker0.reset(broadcast_tracker1)

        _, outputs_cpf_tracker0 = self.cpf_control_tracker0.inputs_outputs()
        _, outputs_cpf_tracker1 = self.cpf_control_tracker1.inputs_outputs()


        # Connection of variables
        # AUV Target
        inputs_kine_target0["u"] = outputs_pf_target0["u"]
        inputs_kine_target1["u"] = outputs_pf_target1["u"]
        inputs_kine_target2["u"] = outputs_pf_target2["u"]
        if t < self.time_halted:
            inputs_kine_target0["velocity"] = 0.0
            inputs_pf_target0["velocity"] = 0.0
            inputs_kine_target1["velocity"] = 0.0
            inputs_pf_target1["velocity"] = 0.0
            inputs_kine_target2["velocity"] = 0.0
            inputs_pf_target2["velocity"] = 0.0
        else:
            inputs_kine_target0["velocity"] = outputs_cpf_target0["velocity"]
            inputs_pf_target0["velocity"] = outputs_cpf_target0["velocity"]
            inputs_kine_target1["velocity"] = outputs_cpf_target1["velocity"]
            inputs_pf_target1["velocity"] = outputs_cpf_target1["velocity"]
            inputs_kine_target2["velocity"] = outputs_cpf_target2["velocity"]
            inputs_pf_target2["velocity"] = outputs_cpf_target2["velocity"]
        inputs_kine_target0["velocity_dot"] = 0
        inputs_kine_target1["velocity_dot"] = 0
        inputs_kine_target2["velocity_dot"] = 0
        
        inputs_pf_target0["x"] = outputs_kine_target0["x"]
        inputs_pf_target0["y"] = outputs_kine_target0["y"]
        inputs_pf_target0["theta_m"] = outputs_kine_target0["theta_m"]
        inputs_pf_target1["x"] = outputs_kine_target1["x"]
        inputs_pf_target1["y"] = outputs_kine_target1["y"]
        inputs_pf_target1["theta_m"] = outputs_kine_target1["theta_m"]
        inputs_pf_target2["x"] = outputs_kine_target2["x"]
        inputs_pf_target2["y"] = outputs_kine_target2["y"]
        inputs_pf_target2["theta_m"] = outputs_kine_target2["theta_m"]
        
        inputs_pf_target0["velocity_dot"] = 0
        inputs_pf_target1["velocity_dot"] = 0
        inputs_pf_target2["velocity_dot"] = 0


        # ASV
        if t < self.time_halted:
            inputs_mpf_tracker0["target_x"] = -4.
            inputs_mpf_tracker0["target_y"] = -10.
            inputs_mpf_tracker0["target_x_dot"] = 0.
            inputs_mpf_tracker0["target_y_dot"] = 0.
            inputs_mpf_tracker1["target_x"] = -4.
            inputs_mpf_tracker1["target_y"] = -10.
            inputs_mpf_tracker1["target_x_dot"] = 0.
            inputs_mpf_tracker1["target_y_dot"] = 0.
        else:
            inputs_mpf_tracker0["target_x"] = outputs_ekf_tracker["x"]
            inputs_mpf_tracker0["target_y"] = outputs_ekf_tracker["y"]
            inputs_mpf_tracker0["target_x_dot"] = outputs_ekf_tracker["x_dot"]
            inputs_mpf_tracker0["target_y_dot"] = outputs_ekf_tracker["y_dot"]
            inputs_mpf_tracker1["target_x"] = outputs_ekf_tracker["x"]
            inputs_mpf_tracker1["target_y"] = outputs_ekf_tracker["y"]
            inputs_mpf_tracker1["target_x_dot"] = outputs_ekf_tracker["x_dot"]
            inputs_mpf_tracker1["target_y_dot"] = outputs_ekf_tracker["y_dot"]

        inputs_mpf_tracker0["target_yaw"] = 0
        inputs_mpf_tracker0["target_u"] = 0
        inputs_mpf_tracker1["target_yaw"] = 0
        inputs_mpf_tracker1["target_u"] = 0
        
        inputs_mpf_tracker0["follower_u"] = outputs_pf_tracker0["u"]
        inputs_mpf_tracker0["follower_velocity"] = outputs_cpf_tracker0["velocity"]
        inputs_mpf_tracker1["follower_u"] = outputs_pf_tracker1["u"]
        inputs_mpf_tracker1["follower_velocity"] = outputs_cpf_tracker1["velocity"]
        
        inputs_pf_tracker0["x"] = outputs_mpf_tracker0["x_ref"]
        inputs_pf_tracker0["y"] = outputs_mpf_tracker0["y_ref"]
        inputs_pf_tracker0["theta_m"] = outputs_mpf_tracker0["theta_m_ref"]
        inputs_pf_tracker0["velocity"] = outputs_cpf_tracker0["velocity"]
        inputs_pf_tracker0["velocity_dot"] = outputs_cpf_tracker0["velocity_dot"]
        inputs_pf_tracker1["x"] = outputs_mpf_tracker1["x_ref"]
        inputs_pf_tracker1["y"] = outputs_mpf_tracker1["y_ref"]
        inputs_pf_tracker1["theta_m"] = outputs_mpf_tracker1["theta_m_ref"]
        inputs_pf_tracker1["velocity"] = outputs_cpf_tracker1["velocity"]
        inputs_pf_tracker1["velocity_dot"] = outputs_cpf_tracker0["velocity_dot"]

        self.cpf_control_tracker0.inputs["gamma0"] = outputs_pf_tracker0["s"]
        self.cpf_control_tracker1.inputs["gamma1"] = outputs_pf_tracker1["s"]



        outputs = {}
        outputs["x_target0"] = outputs_kine_target0["x"]
        outputs["y_target0"] = outputs_kine_target0["y"]
        outputs["theta_m_target0"] = outputs_kine_target0["theta_m"]
        outputs["s_target0"] = outputs_pf_target0["s"]
        outputs["u_target0"] = outputs_pf_target0["u"]
        outputs["x_target1"] = outputs_kine_target1["x"]
        outputs["y_target1"] = outputs_kine_target1["y"]
        outputs["theta_m_target1"] = outputs_kine_target1["theta_m"]
        outputs["s_target1"] = outputs_pf_target1["s"]
        outputs["u_target1"] = outputs_pf_target1["u"]
        outputs["x_target2"] = outputs_kine_target2["x"]
        outputs["y_target2"] = outputs_kine_target2["y"]
        outputs["theta_m_target2"] = outputs_kine_target2["theta_m"]
        outputs["s_target2"] = outputs_pf_target2["s"]
        outputs["u_target2"] = outputs_pf_target2["u"]
        outputs["x_tracker0"] = outputs_mpf_tracker0["x"]
        outputs["y_tracker0"] = outputs_mpf_tracker0["y"]
        outputs["theta_m_tracker0"] = outputs_mpf_tracker0["theta_m"]
        outputs["s_tracker0"] = outputs_pf_tracker0["s"]
        outputs["u_tracker0"] = outputs_pf_tracker0["u"]
        outputs["x_tracker1"] = outputs_mpf_tracker1["x"]
        outputs["y_tracker1"] = outputs_mpf_tracker1["y"]
        outputs["theta_m_tracker1"] = outputs_mpf_tracker1["theta_m"]
        outputs["s_tracker1"] = outputs_pf_tracker1["s"]
        outputs["u_tracker1"] = outputs_pf_tracker1["u"]
        if t < self.time_halted:
            outputs["velocity_target0"] = 0
            outputs["velocity_target1"] = 0
            outputs["velocity_target2"] = 0
        else:
            outputs["velocity_target0"] = outputs_cpf_target0["velocity"]
            outputs["velocity_target1"] = outputs_cpf_target1["velocity"]
            outputs["velocity_target2"] = outputs_cpf_target2["velocity"]
        outputs["velocity_tracker0"] = outputs_cpf_tracker0["velocity"]
        outputs["velocity_tracker1"] = outputs_cpf_tracker1["velocity"]
        outputs["x_ekf"] = outputs_ekf_tracker["x"]
        outputs["y_ekf"] = outputs_ekf_tracker["y"]
        outputs["theta_ekf"] = outputs_ekf_tracker["theta"]
        #print(np.power(outputs_ekf_tracker["x_dot"], 2))
        outputs["velocity_ekf"] = np.sqrt(np.power(outputs_ekf_tracker["x_dot"], 2) + np.power(outputs_ekf_tracker["y_dot"], 2))
        outputs["theta_dot_ekf"] = outputs_ekf_tracker["theta_dot"]
        outputs["range0"] = y_k0
        outputs["range1"] = y_k1

        # Save outputs for plotting
        if self.history:
            for key in self.past_outputs.keys():
                self.past_outputs[key].append(outputs[key])

        self.time.append(t)


        # Update the system
        self.kine_target0.auv_update(inputs_kine_target0, dt=self.dt)
        self.pf_control_target0.pf_update(inputs_pf_target0, dt=self.dt)
        self.cpf_control_target0.cpf_update(dt=self.dt)

        self.kine_target1.auv_update(inputs_kine_target1, dt=self.dt)
        self.pf_control_target1.pf_update(inputs_pf_target1, dt=self.dt)
        self.cpf_control_target1.cpf_update(dt=self.dt)

        self.kine_target2.auv_update(inputs_kine_target2, dt=self.dt)
        self.pf_control_target2.pf_update(inputs_pf_target2, dt=self.dt)
        self.cpf_control_target2.cpf_update(dt=self.dt)


        self.mpf_control_tracker0.mpf_update(inputs_mpf_tracker0, dt=self.dt)
        self.pf_control_tracker0.pf_update(inputs_pf_tracker0, dt=self.dt)
        self.cpf_control_tracker0.cpf_update(dt=self.dt)

        self.mpf_control_tracker1.mpf_update(inputs_mpf_tracker1, dt=self.dt)
        self.pf_control_tracker1.pf_update(inputs_pf_tracker1, dt=self.dt)
        self.cpf_control_tracker1.cpf_update(dt=self.dt)

        return outputs

    def set_initial_conditions(self, init_cond):
        self.kine_target0.set_initial_conditions(init_cond["x_target0"], init_cond["y_target0"], init_cond["theta_m_target0"])
        self.pf_control_target0.set_initial_conditions(init_cond["s_target0"])

        self.kine_target1.set_initial_conditions(init_cond["x_target1"], init_cond["y_target1"], init_cond["theta_m_target1"])
        self.pf_control_target1.set_initial_conditions(init_cond["s_target1"])

        self.kine_target2.set_initial_conditions(init_cond["x_target2"], init_cond["y_target2"], init_cond["theta_m_target2"])
        self.pf_control_target2.set_initial_conditions(init_cond["s_target2"])

        gammas_target = {"gamma0": init_cond["s_target0"], "gamma1": init_cond["s_target1"], "gamma2": init_cond["s_target2"]}
        self.cpf_control_target0.set_initial_conditions(gammas_target)
        self.cpf_control_target1.set_initial_conditions(gammas_target)
        self.cpf_control_target2.set_initial_conditions(gammas_target)


        ry0 = self.mpf_control_tracker0.reference_yaw(init_cond["theta_m_follower0"], init_cond["theta_m_target1"])
        self.mpf_control_tracker0.set_initial_conditions(init_cond["x_follower0"], init_cond["y_follower0"], ry0)
        self.pf_control_tracker0.set_initial_conditions(init_cond["s_follower0"])

        ry1 = self.mpf_control_tracker1.reference_yaw(init_cond["theta_m_follower1"], init_cond["theta_m_target1"])
        self.mpf_control_tracker1.set_initial_conditions(init_cond["x_follower1"], init_cond["y_follower1"], ry1)
        self.pf_control_tracker1.set_initial_conditions(init_cond["s_follower1"])

        gammas_tracker = {"gamma0": init_cond["s_follower0"], "gamma1": init_cond["s_follower1"]}
        self.cpf_control_tracker0.set_initial_conditions(gammas_tracker)
        self.cpf_control_tracker1.set_initial_conditions(gammas_tracker)

        ic_ekf = {
            "x": init_cond["x_target1"],
            "y": init_cond["y_target1"],
            "x_dot": 0,
            "y_dot": 0
        }
        self.ekf_tracker.set_initial_conditions(ic_ekf)

    def past_values(self):
        return (
            self.past_outputs,
            self.kine_target0.past_state,
            self.pf_control_target0.past_state,
            self.cpf_control_target0.past_state,
            self.kine_target1.past_state,
            self.pf_control_target1.past_state,
            self.cpf_control_target1.past_state,
            self.kine_target2.past_state,
            self.pf_control_target2.past_state,
            self.cpf_control_target2.past_state,
            self.mpf_control_tracker0.past_state,
            self.pf_control_tracker0.past_state,
            self.cpf_control_tracker0.past_state,
            self.mpf_control_tracker1.past_state,
            self.pf_control_tracker1.past_state,
            self.cpf_control_tracker1.past_state,
            self.ekf_tracker.past_state
        )













class DoubleASVMPFOnAUVTargetPursuitCF:
    def __init__(self,
                 #path_target0,
                 path_target1,
                 #path_target2,
                 path_tracker0,
                 path_tracker1,
                 pf_params=None,
                 cpf_params_target=None,
                 cpf_params_tracker=None,
                 ekf_params=None,
                 cf_params=None,
                 time_halted=50,
                 etc_type="Time",
                 history=False, dt=1):

        self.dt = dt
        #self.path_target0 = path_target0
        self.path_target1 = path_target1
        #self.path_target2 = path_target2
        self.path_tracker0 = path_tracker0
        self.path_tracker1 = path_tracker1
        self.pf_prarams = pf_params
        self.cpf_params_target = cpf_params_target
        self.cpf_params_tracker = cpf_params_tracker
        self.ekf_params = ekf_params
        self.cf_params = cf_params
        self.time_halted = time_halted

        self.last_cf_ekf_time = 0

        self.time = []
        
        self.history = history
        if history:
            state_history = True
            self.past_outputs = {
                #"x_target0": [],
                #"y_target0": [],
                #"theta_m_target0": [],
                #"s_target0": [],
                # "u_target0": [],
                # "x_pred_target0": [],
                # "y_pred_target0": [],
                "x_target1": [],
                "y_target1": [],
                "theta_m_target1": [],
                "s_target1": [],
                "u_target1": [],
                "x_pred_target1": [],
                "y_pred_target1": [],
                # "x_target2": [],
                # "y_target2": [],
                # "theta_m_target2": [],
                # "s_target2": [],
                # "u_target2": [],
                # "x_pred_target2": [],
                # "y_pred_target2": [],
                "x_tracker0": [],
                "y_tracker0": [],
                "theta_m_tracker0": [],
                "s_tracker0": [],
                "u_tracker0": [],
                "x_tracker1": [],
                "y_tracker1": [],
                "theta_m_tracker1": [],
                "s_tracker1": [],
                "u_tracker1": [],
                # "velocity_target0": [],
                "velocity_target1": [],
                # "velocity_target2": [],
                "velocity_tracker0": [],
                "velocity_tracker1": [],
                "x_ekf": [],
                "y_ekf": [],
                "theta_ekf": [],
                "velocity_ekf": [],
                "theta_dot_ekf": [],
                "range0": [],
                "range1": []
            }
        else:
            state_history = False


        self.A_matrix_target = np.array([[0, 1, 1], [1, 0, 1], [1, 1, 0]])
        self.A_matrix_tracker = np.array([[0, 1], [1, 0]])


        # self.kine_target0 = kn.Kinematics(saturate=0, state_history=state_history, dt=dt)
        # self.pf_control_target0 = pf.Lapierre(some_path=path_target0, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        # self.cpf_control_target0 = cpf.CPFDiscreteControllerETC(num_auv=3, id=0, params=cpf_params_target, k_csi=cpf_params_target["k_csi0"], A_matrix=self.A_matrix_target, etc_type=etc_type, state_history=state_history, dt=dt)
        # self.cf_target0 = cf.ComplementaryFilter(H_matrix=cf_params["H_matrix"], state_history=state_history, dt=dt)
        # self.dms_target0 = cf.DopplerMeasureSimulation(variance=cf_params["doppler_var"], sampling_period=0.1)

        self.kine_target1 = kn.Kinematics(saturate=0, state_history=state_history, dt=dt)
        self.pf_control_target1 = pf.Lapierre(some_path=path_target1, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        # self.cpf_control_target1 = cpf.CPFDiscreteControllerETC(num_auv=3, id=1, params=cpf_params_target, k_csi=cpf_params_target["k_csi1"], A_matrix=self.A_matrix_target, etc_type=etc_type, state_history=state_history, dt=dt)
        self.cf_target1 = cf.ComplementaryFilter(H_matrix=cf_params["H_matrix"], state_history=state_history, dt=dt)
        self.dms_target1 = cf.DopplerMeasureSimulation(variance=cf_params["doppler_var"], sampling_period=0.5)

        # self.kine_target2 = kn.Kinematics(saturate=0, state_history=state_history, dt=dt)
        # self.pf_control_target2 = pf.Lapierre(some_path=path_target2, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        # self.cpf_control_target2 = cpf.CPFDiscreteControllerETC(num_auv=3, id=2, params=cpf_params_target, k_csi=cpf_params_target["k_csi2"], A_matrix=self.A_matrix_target, etc_type=etc_type, state_history=state_history, dt=dt)
        # self.cf_target2 = cf.ComplementaryFilter(H_matrix=cf_params["H_matrix"], state_history=state_history, dt=dt)
        # self.dms_target2 = cf.DopplerMeasureSimulation(variance=cf_params["doppler_var"], sampling_period=0.1)

        
        self.mpf_control_tracker0 = mpf.MovingPathFollowingTest(target_velocity="Multiple", saturate=0, state_history=state_history, dt=dt)
        self.pf_control_tracker0 = pf.Lapierre(some_path=path_tracker0, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        self.cpf_control_tracker0 = cpf.CPFDiscreteControllerETC(num_auv=2, id=0, params=cpf_params_tracker, k_csi=cpf_params_tracker["k_csi0"], A_matrix=self.A_matrix_tracker, etc_type=etc_type, state_history=state_history, dt=dt)
        self.rms_tracker0 = ekf.RangeMeasureSimulation(R=ekf_params["R_matrix"][0][0], sampling_period=2)
        self.ekf_tracker = ekf.ExtendedKalmanFilter(F_matrix=ekf_params["F_matrix"], Q_matrix=ekf_params["Q_matrix"], R_matrix=ekf_params["R_matrix"], dt=dt)
        
        self.mpf_control_tracker1 = mpf.MovingPathFollowingTest(target_velocity="Multiple", saturate=0, state_history=state_history, dt=dt)
        self.pf_control_tracker1 = pf.Lapierre(some_path=path_tracker1, gamma=pf_params["gamma"], k1=pf_params["k1"], k2=pf_params["k2"], k_delta=pf_params["k_delta"], theta_a=pf_params["theta_a"], state_history=state_history, dt=dt)
        self.cpf_control_tracker1 = cpf.CPFDiscreteControllerETC(num_auv=2, id=1, params=cpf_params_tracker, k_csi=cpf_params_tracker["k_csi1"], A_matrix=self.A_matrix_tracker, etc_type=etc_type, state_history=state_history, dt=dt)
        self.rms_tracker1 = ekf.RangeMeasureSimulation(R=ekf_params["R_matrix"][1][1], sampling_period=2)

    def update(self, t):
        # Get dictionaries setup
        # inputs_kine_target0, outputs_kine_target0 = self.kine_target0.inputs_outputs()
        # inputs_pf_target0, outputs_pf_target0 = self.pf_control_target0.inputs_outputs()
        # inputs_cpf_target0, outputs_cpf_target0 = self.cpf_control_target0.inputs_outputs()
        # inputs_cf_target0, outputs_cf_target0 = self.cf_target0.inputs_outputs()

        inputs_kine_target1, outputs_kine_target1 = self.kine_target1.inputs_outputs()
        inputs_pf_target1, outputs_pf_target1 = self.pf_control_target1.inputs_outputs()
        # inputs_cpf_target1, outputs_cpf_target1 = self.cpf_control_target1.inputs_outputs()
        inputs_cf_target1, outputs_cf_target1 = self.cf_target1.inputs_outputs()

        # inputs_kine_target2, outputs_kine_target2 = self.kine_target2.inputs_outputs()
        # inputs_pf_target2, outputs_pf_target2 = self.pf_control_target2.inputs_outputs()
        # inputs_cpf_target2, outputs_cpf_target2 = self.cpf_control_target2.inputs_outputs()
        # inputs_cf_target2, outputs_cf_target2 = self.cf_target2.inputs_outputs()


        inputs_mpf_tracker0, outputs_mpf_tracker0 = self.mpf_control_tracker0.inputs_outputs()
        inputs_pf_tracker0, outputs_pf_tracker0 = self.pf_control_tracker0.inputs_outputs()
        inputs_cpf_tracker0, outputs_cpf_tracker0 = self.cpf_control_tracker0.inputs_outputs()
        inputs_ekf_tracker, outputs_ekf_tracker = self.ekf_tracker.inputs_outputs()

        inputs_mpf_tracker1, outputs_mpf_tracker1 = self.mpf_control_tracker1.inputs_outputs()
        inputs_pf_tracker1, outputs_pf_tracker1 = self.pf_control_tracker1.inputs_outputs()
        inputs_cpf_tracker1, outputs_cpf_tracker1 = self.cpf_control_tracker1.inputs_outputs()


        # self.cpf_control_target0.inputs["gamma0"] = outputs_pf_target0["s"]
        # self.cpf_control_target1.inputs["gamma1"] = outputs_pf_target1["s"]
        # self.cpf_control_target2.inputs["gamma2"] = outputs_pf_target2["s"]

        self.cpf_control_tracker0.inputs["gamma0"] = outputs_pf_tracker0["s"]
        self.cpf_control_tracker1.inputs["gamma1"] = outputs_pf_tracker1["s"]


        # EKF Prediction and Update
        inputs_ekf_tracker["tracker_x0"] = outputs_mpf_tracker0["x"]
        inputs_ekf_tracker["tracker_y0"] = outputs_mpf_tracker0["y"]
        inputs_ekf_tracker["tracker_x1"] = outputs_mpf_tracker1["x"]
        inputs_ekf_tracker["tracker_y1"] = outputs_mpf_tracker1["y"]
        tracker0_pos = np.array([outputs_mpf_tracker0["x"], outputs_mpf_tracker0["y"]])
        tracker1_pos = np.array([outputs_mpf_tracker1["x"], outputs_mpf_tracker1["y"]])
        target_pos = np.array([outputs_kine_target1["x"], outputs_kine_target1["y"]])
        y_k0 = self.rms_tracker0.measurement(t, tracker0_pos, target_pos)
        y_k1 = self.rms_tracker1.measurement(t, tracker1_pos, target_pos)
        if t < 150 or t > 250:
            inputs_ekf_tracker["range0"] = y_k0
            inputs_ekf_tracker["range1"] = y_k1
        else:
            inputs_ekf_tracker["range0"] = None
            inputs_ekf_tracker["range1"] = None

        self.ekf_tracker.ekf_update(inputs_ekf_tracker, t)
        inputs_ekf_tracker, outputs_ekf_tracker = self.ekf_tracker.inputs_outputs()


        # CPF ETC update
        # broadcast_target0 = self.cpf_control_target0.check_update(t)
        # if broadcast_target0 != -1:
        #     self.cpf_control_target1.reset(broadcast_target0)
        #     self.cpf_control_target2.reset(broadcast_target0)

        # broadcast_target1 = self.cpf_control_target1.check_update(t)
        # if broadcast_target1 != -1:
        #     self.cpf_control_target0.reset(broadcast_target1)
        #     self.cpf_control_target2.reset(broadcast_target1)

        # broadcast_target2 = self.cpf_control_target2.check_update(t)
        # if broadcast_target2 != -1:
        #     self.cpf_control_target0.reset(broadcast_target2)
        #     self.cpf_control_target1.reset(broadcast_target2)
        
        # _, outputs_cpf_target0 = self.cpf_control_target0.inputs_outputs()
        # _, outputs_cpf_target1 = self.cpf_control_target1.inputs_outputs()
        # _, outputs_cpf_target2 = self.cpf_control_target2.inputs_outputs()


        broadcast_tracker0 = self.cpf_control_tracker0.check_update(t)
        if broadcast_tracker0 != -1:
            self.cpf_control_tracker1.reset(broadcast_tracker0)

        broadcast_tracker1 = self.cpf_control_tracker1.check_update(t)
        if broadcast_tracker1 != -1:
            self.cpf_control_tracker0.reset(broadcast_tracker1)

        _, outputs_cpf_tracker0 = self.cpf_control_tracker0.inputs_outputs()
        _, outputs_cpf_tracker1 = self.cpf_control_tracker1.inputs_outputs()


        # Connection of variables
        # AUV Target
        # inputs_kine_target0["u"] = outputs_pf_target0["u"]
        inputs_kine_target1["u"] = outputs_pf_target1["u"]
        # inputs_kine_target2["u"] = outputs_pf_target2["u"]
        if t < self.time_halted:
            # inputs_kine_target0["velocity"] = 0.0
            # inputs_pf_target0["velocity"] = 0.0
            inputs_kine_target1["velocity"] = 0.0
            inputs_pf_target1["velocity"] = 0.0
            # inputs_kine_target2["velocity"] = 0.0
            # inputs_pf_target2["velocity"] = 0.0

            # v_w0 = [0, 0]
            v_w1 = [0, 0]
            # v_w2 = [0, 0]
        else:
            # inputs_kine_target0["velocity"] = outputs_cpf_target0["velocity"]
            # inputs_pf_target0["velocity"] = outputs_cpf_target0["velocity"]
            inputs_kine_target1["velocity"] = self.cpf_params_target["speed_profile1"]#outputs_cpf_target1["velocity"]
            inputs_pf_target1["velocity"] = self.cpf_params_target["speed_profile1"]#outputs_cpf_target1["velocity"]
            # inputs_kine_target2["velocity"] = outputs_cpf_target2["velocity"]
            # inputs_pf_target2["velocity"] = outputs_cpf_target2["velocity"]

            # v_w0 = self.dms_target0.measurement(t, outputs_kine_target0["theta_m"], outputs_cpf_target0["velocity"])
            v_w1 = self.dms_target1.measurement(t, outputs_kine_target1["theta_m"], self.cpf_params_target["speed_profile1"])#outputs_cpf_target1["velocity"])
            # v_w2 = self.dms_target2.measurement(t, outputs_kine_target2["theta_m"], outputs_cpf_target2["velocity"])
        # inputs_kine_target0["velocity_dot"] = 0
        inputs_kine_target1["velocity_dot"] = 0
        # inputs_kine_target2["velocity_dot"] = 0
        
        #print(outputs_cf_target0["x_pred"])
        # inputs_pf_target0["x"] = outputs_cf_target0["x_pred"]
        # inputs_pf_target0["y"] = outputs_cf_target0["y_pred"]
        # inputs_pf_target0["theta_m"] = outputs_kine_target0["theta_m"]
        inputs_pf_target1["x"] = outputs_cf_target1["x_pred"]
        inputs_pf_target1["y"] = outputs_cf_target1["y_pred"]
        inputs_pf_target1["theta_m"] = outputs_kine_target1["theta_m"]
        # inputs_pf_target2["x"] = outputs_cf_target2["x_pred"]
        # inputs_pf_target2["y"] = outputs_cf_target2["y_pred"]
        # inputs_pf_target2["theta_m"] = outputs_kine_target2["theta_m"]
        
        # inputs_pf_target0["velocity_dot"] = 0
        inputs_pf_target1["velocity_dot"] = 0
        # inputs_pf_target2["velocity_dot"] = 0
        
        if t - self.last_cf_ekf_time > 5:
            self.last_cf_ekf_time = t
            # inputs_cf_target0["x_EKF"] = outputs_ekf_tracker["x_dot"]
            # inputs_cf_target0["y_EKF"] = outputs_ekf_tracker["y_dot"]
            inputs_cf_target1["x_EKF"] = outputs_ekf_tracker["x"]
            inputs_cf_target1["y_EKF"] = outputs_ekf_tracker["y"]
            # inputs_cf_target2["x_EKF"] = outputs_ekf_tracker["x_dot"]
            # inputs_cf_target2["y_EKF"] = outputs_ekf_tracker["y_dot"]
        else:
            # inputs_cf_target0["x_EKF"] = None
            # inputs_cf_target0["y_EKF"] = None
            inputs_cf_target1["x_EKF"] = None
            inputs_cf_target1["y_EKF"] = None
            # inputs_cf_target2["x_EKF"] = None
            # inputs_cf_target2["y_EKF"] = None

        #print(v_w0)
        # inputs_cf_target0["vx_dop"] = v_w0[0]
        # inputs_cf_target0["vy_dop"] = v_w0[1]
        inputs_cf_target1["vx_dop"] = v_w1[0]
        inputs_cf_target1["vy_dop"] = v_w1[1]
        # inputs_cf_target2["vx_dop"] = v_w2[0]
        # inputs_cf_target2["vy_dop"] = v_w2[1]


        # ASV
        if t < self.time_halted:
            inputs_mpf_tracker0["target_x"] = -4.
            inputs_mpf_tracker0["target_y"] = -10.
            inputs_mpf_tracker0["target_x_dot"] = 0.
            inputs_mpf_tracker0["target_y_dot"] = 0.
            inputs_mpf_tracker1["target_x"] = -4.
            inputs_mpf_tracker1["target_y"] = -10.
            inputs_mpf_tracker1["target_x_dot"] = 0.
            inputs_mpf_tracker1["target_y_dot"] = 0.
        else:
            inputs_mpf_tracker0["target_x"] = outputs_ekf_tracker["x"]
            inputs_mpf_tracker0["target_y"] = outputs_ekf_tracker["y"]
            inputs_mpf_tracker0["target_x_dot"] = outputs_ekf_tracker["x_dot"]
            inputs_mpf_tracker0["target_y_dot"] = outputs_ekf_tracker["y_dot"]
            inputs_mpf_tracker1["target_x"] = outputs_ekf_tracker["x"]
            inputs_mpf_tracker1["target_y"] = outputs_ekf_tracker["y"]
            inputs_mpf_tracker1["target_x_dot"] = outputs_ekf_tracker["x_dot"]
            inputs_mpf_tracker1["target_y_dot"] = outputs_ekf_tracker["y_dot"]

        inputs_mpf_tracker0["target_yaw"] = 0
        inputs_mpf_tracker0["target_u"] = 0
        inputs_mpf_tracker1["target_yaw"] = 0
        inputs_mpf_tracker1["target_u"] = 0
        
        inputs_mpf_tracker0["follower_u"] = outputs_pf_tracker0["u"]
        inputs_mpf_tracker0["follower_velocity"] = outputs_cpf_tracker0["velocity"]
        inputs_mpf_tracker1["follower_u"] = outputs_pf_tracker1["u"]
        inputs_mpf_tracker1["follower_velocity"] = outputs_cpf_tracker1["velocity"]
        
        inputs_pf_tracker0["x"] = outputs_mpf_tracker0["x_ref"]
        inputs_pf_tracker0["y"] = outputs_mpf_tracker0["y_ref"]
        inputs_pf_tracker0["theta_m"] = outputs_mpf_tracker0["theta_m_ref"]
        inputs_pf_tracker0["velocity"] = outputs_cpf_tracker0["velocity"]
        inputs_pf_tracker0["velocity_dot"] = outputs_cpf_tracker0["velocity_dot"]
        inputs_pf_tracker1["x"] = outputs_mpf_tracker1["x_ref"]
        inputs_pf_tracker1["y"] = outputs_mpf_tracker1["y_ref"]
        inputs_pf_tracker1["theta_m"] = outputs_mpf_tracker1["theta_m_ref"]
        inputs_pf_tracker1["velocity"] = outputs_cpf_tracker1["velocity"]
        inputs_pf_tracker1["velocity_dot"] = outputs_cpf_tracker0["velocity_dot"]

        self.cpf_control_tracker0.inputs["gamma0"] = outputs_pf_tracker0["s"]
        self.cpf_control_tracker1.inputs["gamma1"] = outputs_pf_tracker1["s"]



        outputs = {}
        # outputs["x_target0"] = outputs_kine_target0["x"]
        # outputs["y_target0"] = outputs_kine_target0["y"]
        # outputs["theta_m_target0"] = outputs_kine_target0["theta_m"]
        # outputs["s_target0"] = outputs_pf_target0["s"]
        # outputs["u_target0"] = outputs_pf_target0["u"]
        # outputs["x_pred_target0"] = outputs_cf_target0["x_pred"]
        # outputs["y_pred_target0"] = outputs_cf_target0["y_pred"]
        outputs["x_target1"] = outputs_kine_target1["x"]
        outputs["y_target1"] = outputs_kine_target1["y"]
        outputs["theta_m_target1"] = outputs_kine_target1["theta_m"]
        outputs["s_target1"] = outputs_pf_target1["s"]
        outputs["u_target1"] = outputs_pf_target1["u"]
        outputs["x_pred_target1"] = outputs_cf_target1["x_pred"]
        outputs["y_pred_target1"] = outputs_cf_target1["y_pred"]
        # outputs["x_target2"] = outputs_kine_target2["x"]
        # outputs["y_target2"] = outputs_kine_target2["y"]
        # outputs["theta_m_target2"] = outputs_kine_target2["theta_m"]
        # outputs["s_target2"] = outputs_pf_target2["s"]
        # outputs["u_target2"] = outputs_pf_target2["u"]
        # outputs["x_pred_target2"] = outputs_cf_target2["x_pred"]
        # outputs["y_pred_target2"] = outputs_cf_target2["y_pred"]
        outputs["x_tracker0"] = outputs_mpf_tracker0["x"]
        outputs["y_tracker0"] = outputs_mpf_tracker0["y"]
        outputs["theta_m_tracker0"] = outputs_mpf_tracker0["theta_m"]
        outputs["s_tracker0"] = outputs_pf_tracker0["s"]
        outputs["u_tracker0"] = outputs_pf_tracker0["u"]
        outputs["x_tracker1"] = outputs_mpf_tracker1["x"]
        outputs["y_tracker1"] = outputs_mpf_tracker1["y"]
        outputs["theta_m_tracker1"] = outputs_mpf_tracker1["theta_m"]
        outputs["s_tracker1"] = outputs_pf_tracker1["s"]
        outputs["u_tracker1"] = outputs_pf_tracker1["u"]
        if t < self.time_halted:
            # outputs["velocity_target0"] = 0
            outputs["velocity_target1"] = 0
            # outputs["velocity_target2"] = 0
        else:
            # outputs["velocity_target0"] = outputs_cpf_target0["velocity"]
            outputs["velocity_target1"] = self.cpf_params_target["speed_profile1"]#outputs_cpf_target1["velocity"]
            # outputs["velocity_target2"] = outputs_cpf_target2["velocity"]
        outputs["velocity_tracker0"] = outputs_cpf_tracker0["velocity"]
        outputs["velocity_tracker1"] = outputs_cpf_tracker1["velocity"]
        outputs["x_ekf"] = outputs_ekf_tracker["x"]
        outputs["y_ekf"] = outputs_ekf_tracker["y"]
        outputs["theta_ekf"] = outputs_ekf_tracker["theta"]
        #print(np.power(outputs_ekf_tracker["x_dot"], 2))
        outputs["velocity_ekf"] = np.sqrt(np.power(outputs_ekf_tracker["x_dot"], 2) + np.power(outputs_ekf_tracker["y_dot"], 2))
        outputs["theta_dot_ekf"] = outputs_ekf_tracker["theta_dot"]
        outputs["range0"] = y_k0
        outputs["range1"] = y_k1


        # Save outputs for plotting
        if self.history:
            for key in self.past_outputs.keys():
                self.past_outputs[key].append(outputs[key])

        self.time.append(t)


        # Update the system
        # self.kine_target0.auv_update(inputs_kine_target0, dt=self.dt)
        # self.pf_control_target0.pf_update(inputs_pf_target0, dt=self.dt)
        # self.cpf_control_target0.cpf_update(dt=self.dt)
        # self.cf_target0.cf_update(inputs_cf_target0, dt=self.dt)

        self.kine_target1.auv_update(inputs_kine_target1, dt=self.dt)
        self.pf_control_target1.pf_update(inputs_pf_target1, dt=self.dt)
        # self.cpf_control_target1.cpf_update(dt=self.dt)
        self.cf_target1.cf_update(inputs_cf_target1, dt=self.dt)

        # self.kine_target2.auv_update(inputs_kine_target2, dt=self.dt)
        # self.pf_control_target2.pf_update(inputs_pf_target2, dt=self.dt)
        # self.cpf_control_target2.cpf_update(dt=self.dt)
        # self.cf_target2.cf_update(inputs_cf_target2, dt=self.dt)


        self.mpf_control_tracker0.mpf_update(inputs_mpf_tracker0, dt=self.dt)
        self.pf_control_tracker0.pf_update(inputs_pf_tracker0, dt=self.dt)
        self.cpf_control_tracker0.cpf_update(dt=self.dt)

        self.mpf_control_tracker1.mpf_update(inputs_mpf_tracker1, dt=self.dt)
        self.pf_control_tracker1.pf_update(inputs_pf_tracker1, dt=self.dt)
        self.cpf_control_tracker1.cpf_update(dt=self.dt)

        return outputs

    def set_initial_conditions(self, init_cond):
        # self.kine_target0.set_initial_conditions(init_cond["x_target0"], init_cond["y_target0"], init_cond["theta_m_target0"])
        # self.pf_control_target0.set_initial_conditions(init_cond["s_target0"])
        # ic_cf0 = self.cf_target0.state.copy()
        # ic_cf0["x_pred"] = init_cond["x_target0"]
        # ic_cf0["y_pred"] = init_cond["y_target0"]
        # ic_cf0["vcx_pred"] = 0
        # ic_cf0["vcy_pred"] = 0
        # self.cf_target0.set_initial_conditions(ic_cf0)

        self.kine_target1.set_initial_conditions(init_cond["x_target1"], init_cond["y_target1"], init_cond["theta_m_target1"])
        self.pf_control_target1.set_initial_conditions(init_cond["s_target1"])
        ic_cf1 = self.cf_target1.state.copy()
        ic_cf1["x_pred"] = init_cond["x_target1"]
        ic_cf1["y_pred"] = init_cond["y_target1"]
        ic_cf1["vcx_pred"] = 0
        ic_cf1["vcy_pred"] = 0
        self.cf_target1.set_initial_conditions(ic_cf1)

        # self.kine_target2.set_initial_conditions(init_cond["x_target2"], init_cond["y_target2"], init_cond["theta_m_target2"])
        # self.pf_control_target2.set_initial_conditions(init_cond["s_target2"])
        # ic_cf2 = self.cf_target2.state.copy()
        # ic_cf2["x_pred"] = init_cond["x_target2"]
        # ic_cf2["y_pred"] = init_cond["y_target2"]
        # ic_cf2["vcx_pred"] = 0
        # ic_cf2["vcy_pred"] = 0
        # self.cf_target2.set_initial_conditions(ic_cf2)

        # gammas_target = {"gamma0": init_cond["s_target0"], "gamma1": init_cond["s_target1"], "gamma2": init_cond["s_target2"]}
        # self.cpf_control_target0.set_initial_conditions(gammas_target)
        # self.cpf_control_target1.set_initial_conditions(gammas_target)
        # self.cpf_control_target2.set_initial_conditions(gammas_target)


        ry0 = self.mpf_control_tracker0.reference_yaw(init_cond["theta_m_follower0"], init_cond["theta_m_target1"])
        self.mpf_control_tracker0.set_initial_conditions(init_cond["x_follower0"], init_cond["y_follower0"], ry0)
        self.pf_control_tracker0.set_initial_conditions(init_cond["s_follower0"])

        ry1 = self.mpf_control_tracker1.reference_yaw(init_cond["theta_m_follower1"], init_cond["theta_m_target1"])
        self.mpf_control_tracker1.set_initial_conditions(init_cond["x_follower1"], init_cond["y_follower1"], ry1)
        self.pf_control_tracker1.set_initial_conditions(init_cond["s_follower1"])

        gammas_tracker = {"gamma0": init_cond["s_follower0"], "gamma1": init_cond["s_follower1"]}
        self.cpf_control_tracker0.set_initial_conditions(gammas_tracker)
        self.cpf_control_tracker1.set_initial_conditions(gammas_tracker)

        ic_ekf = {
            "x": init_cond["x_target1"],
            "y": init_cond["y_target1"],
            "x_dot": 0,
            "y_dot": 0
        }
        self.ekf_tracker.set_initial_conditions(ic_ekf)

    def past_values(self):
        return (
            self.past_outputs,
            # self.kine_target0.past_state,
            # self.pf_control_target0.past_state,
            # self.cpf_control_target0.past_state,
            # self.cf_target0.past_state,
            self.kine_target1.past_state,
            self.pf_control_target1.past_state,
            # self.cpf_control_target1.past_state,
            self.cf_target1.past_state,
            # self.kine_target2.past_state,
            # self.pf_control_target2.past_state,
            # self.cpf_control_target2.past_state,
            # self.cf_target2.past_state,
            self.mpf_control_tracker0.past_state,
            self.pf_control_tracker0.past_state,
            self.cpf_control_tracker0.past_state,
            self.mpf_control_tracker1.past_state,
            self.pf_control_tracker1.past_state,
            self.cpf_control_tracker1.past_state,
            self.ekf_tracker.past_state
        )