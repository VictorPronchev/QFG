# QFG Dynamics 0.3.1 Render Hotfix

`QFG_Dynamics_Core` is a Gaussian field emitter represented by a Blender sphere
for authoring. In 0.3.0 this proxy was still visible to the camera. Because the
camera could be inside that large sphere, the entire result appeared as a pale
blue or grey frame.

Version 0.3.1 makes source actors viewport-only:

```python
obj.display_type = "WIRE"
obj.show_in_front = True
obj.hide_render = True
```

The numerical field remains visible through `QFG_Field_Points`.
