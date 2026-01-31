from digitloom.constants import format_spigot_pi


PI_50 = "3.14159265358979323846264338327950288419716939937510"


def test_spigot_pi_prefix():
    assert format_spigot_pi(51) == PI_50
