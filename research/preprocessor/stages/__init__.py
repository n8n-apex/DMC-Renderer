"""Pre-processor stages.

Stage 1: validate_input — REJECT LOUD on missing required fields;
         map client.brand_hex_* → chassis BrandConfig 10-field shape;
         check page_count ∈ {16,20,24,28}; check ≥3 ST-07A;
         check FIXED slots S1=ST-01 S20=ST-03.

Stage 2: resolve_fonts — default Montserrat + Source Sans 3 (chassis
         Priorität-2 system fonts); flag customer-upload-needed when
         a different font is requested.

Phase A stops here. Stages 3-8 are later phases.
"""
