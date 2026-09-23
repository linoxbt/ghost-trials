"""MuJoCo ground-contact friction intervention, independent of model inference.

The whole ground changes at onset; this is not a spatial fluid simulation.
Explicit contact pairs and geom priorities are handled so the robot's original
friction cannot silently override the intended ground coefficient.
"""
import math


class GroundTraction:
    def __init__(self, model, coefficient: float):
        import mujoco
        import numpy as np
        if not math.isfinite(coefficient) or not .01 <= coefficient <= 1:
            raise ValueError("Sliding friction must be in [0.01, 1]")
        self.model, self.coefficient = model, coefficient
        self.ground = [i for i in range(model.ngeom) if model.geom_type[i] == mujoco.mjtGeom.mjGEOM_PLANE
                       and model.geom_bodyid[i] == 0 and (model.geom_contype[i] or model.geom_conaffinity[i])]
        if not self.ground:
            raise ValueError("Traction trial requires a collision-enabled, static world plane")
        self.friction = model.geom_friction.copy()
        self.priority = model.geom_priority.copy()
        self.pair_friction = model.pair_friction.copy()
        self.pairs = [i for i in range(model.npair) if model.pair_geom1[i] in self.ground or model.pair_geom2[i] in self.ground]
        if any(model.pair_dim[i] < 3 for i in self.pairs):
            raise ValueError("Ground contact pair disables tangential friction")
        self.new_priority = int(np.max(model.geom_priority)) + 1
        self.active = False

    def activate(self):
        self.model.geom_friction[self.ground, 0] = self.coefficient
        self.model.geom_priority[self.ground] = self.new_priority
        for pair in self.pairs:
            self.model.pair_friction[pair, :2] = self.coefficient
        self.active = True

    def restore(self):
        self.model.geom_friction[:] = self.friction
        self.model.geom_priority[:] = self.priority
        self.model.pair_friction[:] = self.pair_friction
        self.active = False

    def observe(self, data, robot_geoms):
        import mujoco
        import numpy as np
        speeds, friction = [], []
        for contact in data.contact:
            a, b = int(contact.geom1), int(contact.geom2)
            robot = b if a in self.ground and b in robot_geoms else a if b in self.ground and a in robot_geoms else None
            if robot is None or contact.dist > 0:
                continue
            velocity = np.zeros(6)
            mujoco.mj_objectVelocity(self.model, data, mujoco.mjtObj.mjOBJ_GEOM, robot, velocity, 0)
            point_velocity = velocity[3:] + np.cross(velocity[:3], contact.pos - data.geom_xpos[robot])
            normal = contact.frame[:3]
            speeds.append(float(np.linalg.norm(point_velocity - normal * np.dot(point_velocity, normal))))
            friction.append(float(contact.friction[0]))
        if self.active and friction and any(abs(mu - self.coefficient) > 1e-6 for mu in friction):
            raise RuntimeError("Observed ground contact friction does not match the injected coefficient")
        return {"contact_slip_speed_m_s": max(speeds) if speeds else None,
                "effective_friction": min(friction) if friction else None,
                "ground_contact_count": len(speeds)}
