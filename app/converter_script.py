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
        print(f"Mesh loaded. Points: {mesh.CountPoints}, Facets: {mesh.CountFacets}")
        
        print("Analyzing and repairing mesh...")
        # Smart repair steps
        # 1. Harmonize normals (ensure all face normals point outwards)
        mesh.harmonizeNormals()
        print("Normals harmonized.")
        
        # 2. Remove non-manifolds (geometry that can't exist in real world)
        mesh.removeNonManifolds()
        print("Non-manifolds removed.")
        
        # 3. Fix self-intersections
        mesh.fixSelfIntersections()
        print("Self-intersections fixed.")
        
        # 4. Fix indices and degenerations (common issues)
        mesh.fixIndices()
        mesh.fixDegenerations()
        print("Indices and degenerations fixed.")
        
        # Note: fillupHoles is not a direct method on the mesh object in all versions.
        # We rely on the other fix methods to make it solid enough.
        
        # Check if mesh is closed
        if not mesh.isSolid():
            print("Warning: Mesh is not a closed solid. Attempting to proceed, but result might be a shell.")
        else:
            print("Mesh is a valid solid.")
        
        print("Converting mesh to shape...")
        shape = Part.Shape()
        # Tolerance is a key parameter. 
        # Too small = too many faces, slow, might fail.
        # Too large = loss of detail.
        # 0.05 is a reasonable default for STL conversion.
        shape.makeShapeFromMesh(mesh.Topology, 0.05) 
        print("Shape created from mesh.")
        
        print("Converting shape to solid...")
        solid = Part.makeSolid(shape)
        print("Solid created.")
        
        print("Refining shape (cleaning up redundant edges)...")
        solid = solid.removeSplitter()
        print("Shape refined.")
        
        print(f"Exporting to {output_path}...")
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        solid.exportStep(output_path)
        print(f"Export completed to {output_path}")
        
        if os.path.exists(output_path):
             print(f"Verification: File exists and size is {os.path.getsize(output_path)} bytes.")
        else:
             print("Verification FAILED: File does not exist after export.")
        
        print("Conversion successful.")
        
    except Exception as e:
        print(f"Error during conversion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # When running via FreeCADCmd, the arguments passed after the script name are in sys.argv
    # However, FreeCADCmd treats non-flag arguments as files to open.
    # To avoid this, we need to inspect sys.argv carefully.
    
    # sys.argv usually looks like: ['freecadcmd', 'script.py', 'arg1', 'arg2']
    # But FreeCAD might try to open arg1 and arg2.
    
    # We will look for our specific arguments.
    # We expect 2 arguments: input_file and output_file
    
    args = sys.argv[2:] # Skip executable and script name
    
    if len(args) < 2:
        print("Usage: FreeCADCmd.exe <script_path> <input_file> <output_file>")
        print(f"Received args: {sys.argv}")
        # We don't exit with error here because FreeCAD might have injected other args
        # But we can't proceed without input/output
        sys.exit(1)
        
    input_file = args[0]
    output_file = args[1]
    
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)
    
    convert(input_file, output_file)
    
    # Exit FreeCAD cleanly
    sys.exit(0)
