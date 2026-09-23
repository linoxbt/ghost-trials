import xml.etree.ElementTree as ET

from workers.isaac.sonic_trial import build_scene


def test_scene_preserves_included_asset_paths_and_appends_hazard(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "robot.xml").write_text('<mujoco><compiler meshdir="meshes"/><worldbody><body name="pelvis"><freejoint name="floating_base_joint"/></body></worldbody></mujoco>')
    (source / "scene.xml").write_text('<mujoco><include file="robot.xml"/><worldbody><geom name="floor" type="plane" size="0 0 .05"/></worldbody></mujoco>')
    output = tmp_path / "new-scene.xml"
    build_scene(source / "scene.xml", output)
    scene = ET.parse(output).getroot()
    assert not scene.findall(".//include")
    assert scene.find("compiler").get("meshdir") == str(source / "meshes")
    assert [joint.get("name") for joint in scene.findall(".//freejoint")] == ["floating_base_joint", "ghost_free"]
    assert scene.find(".//geom[@name='ghost_box_geom']").get("mass") == "2"
