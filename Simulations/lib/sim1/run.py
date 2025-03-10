"""

Author: Francisco Branco
Created: 24/08/2021

"""


import numpy as np
import pickle
from math import pi

import pathgeneration as pg
import lib.sim1.systembuild as sb
import lib.sim1.plot as plotting


def simulation(file_name):
    if file_name != "":
        f = open("lib\sim1\\" + file_name + ".txt", 'wb')

    # Path parameters
    resolution = 40
    start = 0
    position = np.array([10, 5])
    orientation = -pi/2
    size = 25.0
    arc = 2*pi
    radius = size

    # Path creation
    p1 = pg.Path()
    circle1 = pg.Circle(resolution, position, orientation, arc, radius, start)
    p1.append_path(circle1)

    # Time parameters
    total_time = 200
    num_points = total_time * 20
    T, dt = np.linspace(start=0, stop=total_time, num=num_points, retstep=True)

    # Vehicle initial conditions
    x = 5
    y = 0
    theta_m = 0
    s = 0


    # System creation along with initial conditions
    auv_pf_system = sb.SimpleAUVPathFollowing(some_path=p1, gamma=1, k1=1, k2=0.3, k_delta=0.5, theta_a=0.8, history=True, dt=dt)
    ic = {"x": x, "y": y, "theta_m": theta_m, "s": s}
    auv_pf_system.set_initial_conditions(ic)

    # Setup external inputs
    velocity = 0.8
    velocity_dot = 0
    inputs = {"velocity": velocity, "velocity_dot": velocity_dot}

    # Run the system
    for t in T:
        auv_pf_system.update(t, inputs)

    # Get past values for plotting
    past_values = auv_pf_system.past_values()

    paths = {"p1": p1}

    if file_name != "":
        pickle.dump(paths, f)
        pickle.dump(num_points, f)
        pickle.dump(total_time, f)
        pickle.dump(resolution, f)
        pickle.dump(T, f)
        pickle.dump(past_values, f)
        f.close()

    # Plotting
    plotting.plot(paths, num_points, total_time, resolution, T, past_values)