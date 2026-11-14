class_name VisitorModel
extends Node3D
## A V0 greybox visitor: a faceted capsule with a dark eye band showing which way the head
## faces (Blueprint §5.2), and a name tag. Colors are neutral and never encode role, worth
## or intent (ART_DIRECTION §2.2).


static func create(radius_m: float, height_m: float, color_name: String, tag_text: String) -> VisitorModel:
	var m := VisitorModel.new()
	m.name = "VisitorModel"
	var capsule := CapsuleMesh.new()
	capsule.radius = radius_m
	capsule.height = height_m
	capsule.radial_segments = 8
	capsule.rings = 2
	m.add_child(MeshKit.mesh_instance(MeshKit.faceted(capsule), Palette.material(color_name), "Body", Vector3(0, height_m / 2, 0)))
	var head := Node3D.new()
	head.name = "Head"
	head.position = Vector3(0, height_m - 0.2, 0)
	m.add_child(head)
	head.add_child(MeshKit.mesh_instance(MeshKit.box_mesh(Vector3(radius_m * 1.1, 0.07, 0.08)),
		Palette.material("visitor_face"), "EyeBand", Vector3(0, 0, -(radius_m - 0.025))))
	var tag := MeshKit.label(tag_text, 40)
	tag.name = "NameTag"
	tag.position = Vector3(0, height_m + 0.3, 0)
	m.add_child(tag)
	return m
