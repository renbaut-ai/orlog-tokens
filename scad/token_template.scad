// Orlog God's Favor Token Template
// Generates 3D printable token with front relief and back engravings

// ============ PARAMETERS (set per token) ============
// These get overridden by the generator script
god_name = "THOR";
tier1 = "4: Deal 2 dmg";
tier2 = "8: Deal 5 dmg";
tier3 = "12: Deal 8 dmg";
heightmap_file = "thors_strike.png";
heightmap_width = 200;  // pixels
heightmap_height = 348; // pixels

// ============ DIMENSIONS (mm) ============
token_width = 28.575;      // 1.125"
token_height = 59.53;      // 2.34375"  
token_depth = 3.175;       // 0.125"

relief_depth = 1.2;        // How deep the front relief goes
engrave_depth = 0.6;       // How deep back text is engraved
base_thickness = 1.0;      // Minimum thickness at lowest relief point

// ============ TABLET SHAPE ============
// Rounded top, angular bottom corners (like the original tokens)

module tablet_outline_2d() {
    w = token_width;
    h = token_height;
    corner_cut = 2.5;  // Bottom corner chamfer
    top_radius = w * 0.5;  // Rounded top
    
    hull() {
        // Top rounded part
        translate([w/2, h - top_radius])
            resize([w, top_radius * 1.2])
                circle(d=w, $fn=64);
        
        // Main body
        translate([corner_cut, 0])
            square([w - corner_cut*2, h * 0.7]);
        
        // Bottom with chamfered corners
        polygon([
            [corner_cut, 0],
            [w - corner_cut, 0],
            [w, corner_cut],
            [w, h * 0.3],
            [0, h * 0.3],
            [0, corner_cut]
        ]);
    }
}

// Base tablet solid
module tablet_base() {
    linear_extrude(height = token_depth)
        tablet_outline_2d();
}

// ============ FRONT RELIEF ============
// Uses heightmap PNG - white=high, black=low

module front_relief() {
    // Scale factors to fit heightmap to token dimensions
    scale_x = token_width / heightmap_width;
    scale_y = token_height / heightmap_height;
    scale_z = relief_depth / 255;  // PNG values 0-255
    
    translate([0, 0, base_thickness])
    scale([scale_x, scale_y, scale_z])
        surface(file = heightmap_file, center = false, convexity = 5);
}

// ============ BACK ENGRAVINGS ============

module token_symbol() {
    // Bowen knot / Celtic knot symbol (simplified)
    // This is a 4-lobed design
    size = 6;
    thickness = 1.2;
    
    for (i = [0:3]) {
        rotate([0, 0, i * 90])
        translate([size/3, 0, 0])
            circle(d = size/2, $fn=32);
    }
    circle(d = size/3, $fn=32);
}

module back_text() {
    font_name = "Arial:style=Bold";
    
    // God name at top
    translate([token_width/2, token_height - 8, 0])
        text(god_name, size=4, halign="center", valign="center", font=font_name, $fn=32);
    
    // Token symbol in middle
    translate([token_width/2, token_height/2 + 5, 0])
        token_symbol();
    
    // Tier costs
    translate([token_width/2, token_height/2 - 8, 0])
        text(tier1, size=2.5, halign="center", valign="center", font=font_name, $fn=24);
    
    translate([token_width/2, token_height/2 - 14, 0])
        text(tier2, size=2.5, halign="center", valign="center", font=font_name, $fn=24);
    
    translate([token_width/2, token_height/2 - 20, 0])
        text(tier3, size=2.5, halign="center", valign="center", font=font_name, $fn=24);
}

module back_engravings() {
    // Extrude text for subtraction
    linear_extrude(height = engrave_depth + 0.1)
        back_text();
}

// ============ FINAL TOKEN ============

module token() {
    difference() {
        union() {
            // Base tablet
            tablet_base();
            
            // Front relief (additive)
            intersection() {
                front_relief();
                // Clip to tablet outline
                linear_extrude(height = token_depth + relief_depth)
                    tablet_outline_2d();
            }
        }
        
        // Back engravings (subtractive) 
        // Position at z=0, facing down (back of token)
        translate([0, 0, -0.1])
            mirror([0, 0, 1])
                translate([0, 0, -engrave_depth])
                    back_engravings();
    }
}

// Render the token
token();
