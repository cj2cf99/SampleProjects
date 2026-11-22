"""Add rest-space color masks to the source's existing packed textures."""

import math
from pathlib import Path
import sys

import bpy


def rgb(hex_code):
    values=(int(hex_code[i:i+2],16)/255 for i in (0,2,4))
    return tuple(x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in values)+(1.,)


def smooth(t):
    t=min(1.,max(0.,t))
    return t*t*(3.-2.*t)


def attr(mesh,name,values):
    channel=mesh.attributes.get(name) or mesh.attributes.new(name,"FLOAT","POINT")
    channel.data.foreach_set("value",list(values))


def shader(name,image_name):
    material=bpy.data.materials[name]
    nodes=material.node_tree.nodes
    nodes.clear()
    links=material.node_tree.links
    texture=nodes.new("ShaderNodeTexImage")
    texture.image=bpy.data.images[image_name]
    surface=nodes.new("ShaderNodeBsdfPrincipled")
    out=nodes.new("ShaderNodeOutputMaterial")
    links.new(surface.outputs[0],out.inputs["Surface"])
    surface.inputs["Specular IOR Level"].default_value=.31
    surface.inputs["Roughness"].default_value=.42
    surface.inputs["Coat Weight"].default_value=.08
    surface.inputs["Emission Strength"].default_value=.075
    return nodes,links,texture.outputs["Color"],surface


def field(nodes,name):
    node=nodes.new("ShaderNodeAttribute")
    node.attribute_name=name
    return node.outputs["Fac"]


def ramp(nodes,links,source,points):
    item=nodes.new("ShaderNodeValToRGB")
    item.color_ramp.interpolation="EASE"
    for i,(position,color) in enumerate(points):
        point=item.color_ramp.elements[i] if i<2 else item.color_ramp.elements.new(position)
        point.position=position
        point.color=rgb(color) if isinstance(color,str) else color
    links.new(source,item.inputs["Fac"])
    return item.outputs["Color"]


def blend(nodes,links,left,right,factor,operation="MIX"):
    n=nodes.new("ShaderNodeMixRGB")
    n.blend_type=operation
    for index,value in enumerate((factor,left,right)):
        if isinstance(value,bpy.types.NodeSocket):
            links.new(value,n.inputs[index])
        else:
            n.inputs[index].default_value=value
    return n.outputs[0]


def math_node(nodes,links,operation,a,b=None):
    node=nodes.new("ShaderNodeMath")
    node.operation=operation
    for index,value in enumerate((a,b)):
        if value is None:
            continue
        if isinstance(value,bpy.types.NodeSocket):
            links.new(value,node.inputs[index])
        else:
            node.inputs[index].default_value=value
    return node.outputs[0]


def color_surface(links,surface,color):
    links.new(color,surface.inputs["Base Color"])
    links.new(color,surface.inputs["Emission Color"])


def hair():
    rig=bpy.data.objects["Mermaid Anime"]
    for name in ("Hair","Hair tails"):
        obj=bpy.data.objects[name]
        bind=rig.matrix_world.inverted()@obj.matrix_world
        attr(obj.data,"Hair root to tip",(smooth((1.712-(bind@point.co).z)/.57) for point in obj.data.vertices))
    n,l,texture,p=shader("hair","hair")
    root=field(n,"Hair root to tip")
    palette=ramp(n,l,root,((0.,"974950"),(1.,"F1A27D"),(.24,"C65B58"),(.61,"E18471")))
    # The atlas keeps its painted strand separation in the tint.
    painted=blend(n,l,palette,texture,.71,"MULTIPLY")
    color_surface(l,p,painted)
    p.inputs["Roughness"].default_value=.59
    p.inputs["Specular IOR Level"].default_value=.095
    p.inputs["Coat Weight"].default_value=0.
    p.inputs["Emission Strength"].default_value=.15


def body():
    mesh=bpy.data.objects["mermaid"].data
    coords=[tuple(v.co) for v in mesh.vertices]
    attr(mesh,"Tail mask",(smooth((1.158-z)/.144) for x,y,z in coords))
    attr(mesh,"Tail gradient",((1.10-z)/1.45 for x,y,z in coords))
    attr(mesh,"Scale circumference",(math.atan2(max(0.,x),-y+.003)/math.pi for x,y,z in coords))
    attr(mesh,"Scale length",((1.075-z)/1.16 for x,y,z in coords))
    attr(mesh,"Scale area",(smooth((z-.04)/.17)*smooth((1.12-z)/.15) for x,y,z in coords))
    attr(mesh,"Fin membrane",(smooth((.033-z)/.33) for x,y,z in coords))
    attr(mesh,"Ear fin mask",(smooth((abs(x)-.069)/.045)*smooth((z-1.55)/.03) for x,y,z in coords))
    attr(mesh,"Ear fin edge",(smooth((abs(x)-.086)/.063) for x,y,z in coords))
    n,l,texture,p=shader("base skin","mermaid skin.png")
    skin=blend(n,l,texture,rgb("FFE4D5"),.37,"MULTIPLY")
    ear=ramp(n,l,field(n,"Ear fin edge"),((0.,"94E3CB"),(1.,"D8A6D6"),(.56,"9DC9E2")))
    skin=blend(n,l,skin,blend(n,l,ear,texture,.60,"MULTIPLY"),field(n,"Ear fin mask"))
    tail=field(n,"Tail mask")
    pattern=ramp(n,l,field(n,"Tail gradient"),((0.,"36AB80"),(1.,"D1A6E2"),(.22,"27977F"),
                                                    (.50,"168995"),(.72,"34699F"),(.89,"70C8BF")))
    dye=blend(n,l,pattern,texture,.68,"MULTIPLY")
    op=lambda operation,a,b=None: math_node(n,l,operation,a,b)
    v=op("MULTIPLY",field(n,"Scale length"),29.)
    u=op("MULTIPLY",field(n,"Scale circumference"),13.)
    row=op("FLOOR",v)
    odd=op("MODULO",row,2.)
    offset=op("MULTIPLY",odd,.50)
    across=op("SUBTRACT",op("FRACT",op("ADD",u,offset)),.50)
    curve=op("ADD",.23,op("MULTIPLY",op("MULTIPLY",across,across),1.15))
    gap=op("ABSOLUTE",op("SUBTRACT",op("FRACT",v),curve))
    line=ramp(n,l,gap,((.015,(.36,.36,.36,1)),(.071,(0.,0.,0.,1))))
    covered=op("MULTIPLY",line,field(n,"Scale area"))
    dye=blend(n,l,dye,rgb("497372"),covered,"MULTIPLY")
    color=blend(n,l,skin,dye,tail)
    color_surface(l,p,color)
    l.new(op("SUBTRACT",.49,op("MULTIPLY",tail,.17)),p.inputs["Roughness"])
    l.new(op("ADD",.045,op("MULTIPLY",tail,.15)),p.inputs["Coat Weight"])
    l.new(op("MULTIPLY",field(n,"Fin membrane"),.075),p.inputs["Subsurface Weight"])


def top():
    obj=bpy.data.objects["bikini "]
    attr(obj.data,"Woven edge",
         (max(smooth((1.327-v.co.z)/.024),smooth((v.co.z-1.417)/.030),
              .65*smooth((.025-abs(v.co.x))/.023)*smooth((v.co.z-1.343)/.027))
          for v in obj.data.vertices))
    n,l,texture,p=shader("outfit","outfit mermaid.png")
    palette=ramp(n,l,field(n,"Woven edge"),((0.,"534066"),(1.,"DDB378"),(.38,"854A72")))
    color_surface(l,p,blend(n,l,palette,texture,.46,"MULTIPLY"))
    p.inputs["Roughness"].default_value=.37


def main():
    out=Path(sys.argv[sys.argv.index("--")+1]).resolve()
    out.mkdir(parents=True,exist_ok=True)
    scene=bpy.context.scene
    scene.frame_set(349)
    hair()
    body()
    top()
    bpy.data.lights["Front fill"].color=(1.,.95,.89)
    scene.frame_set(1)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(out/"Mermaid_color.blend"))
    scene.render.resolution_percentage=66
    for frame in (52,235,401):
        scene.frame_set(frame)
        scene.render.filepath=str(out/f"color_{frame:04d}.png")
        bpy.ops.render.render(write_still=True)


if __name__=="__main__":
    main()
