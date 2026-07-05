## Sample standard: prefer explicit exit codes

Scripts and CLI tools must exit non-zero on failure and document every exit
code they emit. Silent success on a failed operation is treated as a defect.
