import sys
import os

# FreeCAD imports are implicitly available when running via FreeCADCmd, 
# but we import them to be explicit and for linter support if configured.
try:
    import FreeCAD
    import Part
    import Mesh
except ImportError:
    print("Error: This script must be run within the FreeCAD environment (FreeCADCmd).")
    sys.exit(1)

def convert(input_path, output_path):
    try:
        print(f"Opening {input_path}...")
        mesh = Mesh.Mesh(input_path)
        
        print("Analyzing and repairing mesh...")
        # Smart repair steps
        # 1. Harmonize normals (ensure all face normals point outwards)
        mesh.harmonizeNormals()
        
        # 2. Remove non-manifolds (geometry that can't exist in real world)
        mesh.removeNonManifolds()
        
        # 3. Fix self-intersections
        mesh.fixSelfIntersections()
        
        # 4. Fill holes (make it watertight)
        mesh.fillHoles()
        
        # Check if mesh is closed
        if not mesh.isSolid():
            print("Warning: Mesh is not a closed solid. Attempting to proceed, but result might be a shell.")
        
        print("Converting mesh to shape...")
        shape = Part.Shape()
        # Tolerance is a key parameter. 
        # Too small = too many faces, slow, might fail.
        # Too large = loss of detail.
        # 0.05 is a reasonable default for STL conversion.
        shape.makeShapeFromMesh(mesh.Topology, 0.05) 
        
        print("Converting shape to solid...")
        solid = Part.makeSolid(shape)
        
        print("Refining shape (cleaning up redundant edges)...")
        solid = solid.removeSplitter()
        
        print(f"Exporting to {output_path}...")
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        solid.exportStep(output_path)
        
        print("Conversion successful.")
        
    except Exception as e:
        print(f"Error during conversion: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # When running via FreeCADCmd, the arguments passed after the script name are in sys.argv
    # sys.argv[0] is the script path
    
    if len(sys.argv) < 3:
        print("Usage: FreeCADCmd.exe <script_path> <input_file> <output_file>")
        print(f"Received args: {sys.argv}")
        sys.exit(1)
        
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)
    
    convert(input_file, output_file)
