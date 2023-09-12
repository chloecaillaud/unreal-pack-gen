NOTE: this file is an example, and is not required for the functioning of the tool

Setup Guide:
===================
Install to engine for easy import to any projects in version

1. unzip the pack
2. Locate the install location of the Unreal engine version you wish to use
     Default paths:
       Windows: C:\Program Files\Epic Games\UE_*
       MacOS:   /Users/Shared/Epic Games/UE_*
       Linux:   ¯\_(ツ)_/¯

3. Move all files into their respective folders:
   (pack)/FeaturePacks/* -> (engine)/FeaturePacks/
   (pack)/Samples/*      -> (engine)/Samples/

   Note: Steps 1 and 3 can also be achieved by extracting the zipped pack directly into the engine folder and discarding any additional files not mentioned above

4. Open any project (of the correct version) you wish to import this pack into
5. In the Content Browser click +Add > Add Feature or Content Pack
6. Find the pack
7. Click add to project

Troubleshoot:
===================
Asset failed to import/ pack not showing in editor
---------
- Ensure you are using a supported Version (see top of this file for supported versions)
- Ensure all files have been correctly unzipped
- Ensure files are placed into the correct folders in the engine
   - /FeaturePacks/ should contain .upack file(s)
   - /Samples/ should contain a folder structure (ex: packname/Content/...)
- Ensure project and engine version match