pub fn get_art(species: &str, _stage: &str, mood: &str) -> String {
    match species.to_lowercase().as_str() {
        "cat" => cat_art(mood),
        "dog" => dog_art(mood),
        "dragon" => dragon_art(mood),
        "fox" => fox_art(mood),
        "whale" => whale_art(mood),
        _ => generic_art(mood),
    }
}

fn cat_art(mood: &str) -> String {
    match mood {
        "happy" => "  /\\_/\\\n ( ^.^ )\n  > ^ <\n",
        "sad" => "  /\\_/\\\n ( ;.; )\n  > ^ <\n",
        "sick" => "  /\\_/\\\n ( x.x )\n  > ^ <\n",
        _ => "  /\\_/\\\n ( o.o )\n  > ^ <\n",
    }.to_string()
}

fn dog_art(mood: &str) -> String {
    match mood {
        "happy" => "   __\n  /  \\\n |    |\n  \\__/\n",
        "sad" => "   __\n  /  \\\n | .. |\n  \\__/\n",
        "sick" => "   __\n  /  \\\n | XX |\n  \\__/\n",
        _ => "   __\n  /  \\\n |    |\n  \\__/\n",
    }.to_string()
}

fn dragon_art(mood: &str) -> String {
    match mood {
        "happy" => r"  /\_/\
 ( ^.^ )
  >   <
  ~~~",
        "sad" => r"  /\_/\
 ( u.u )
  >   <
  ~~~",
        "sick" => r"  /\_/\
 ( 0.0 )
  >   <
  ~~~",
        _ => r"  /\_/\
 ( o.o )
  >   <
  ~~~",
    }.to_string()
}

fn fox_art(mood: &str) -> String {
    match mood {
        "happy" => r"  /\
 ( ^.^ )
  > ^ <",
        "sad" => r"  /\
 ( ;.; )
  > ^ <",
        "sick" => r"  /\
 ( x.x )
  > ^ <",
        _ => r"  /\
 ( o.o )
  > ^ <",
    }.to_string()
}

fn whale_art(mood: &str) -> String {
    match mood {
        "happy" => r"   .--.
  (    )
  '~~~~'",
        "sad" => r"   .--.
  ( .. )
  '~~~~'",
        "sick" => r"   .--.
  ( XX )
  '~~~~'",
        _ => r"   .--.
  (    )
  '~~~~'",
    }.to_string()
}

fn generic_art(mood: &str) -> String {
    match mood {
        "happy" => "  :-)\n",
        "sad" => "  :-(\n",
        "sick" => "  :-S\n",
        _ => "  :-|\n",
    }.to_string()
}