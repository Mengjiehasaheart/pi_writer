from digitloom.bbp import pi_hex_digit, pi_hex_digits


def test_pi_hex_digits_prefix():
    assert pi_hex_digits(0, 16) == "243F6A8885A308D3"


def test_pi_hex_single_digits():
    assert pi_hex_digit(0) == 2
    assert pi_hex_digit(1) == 4
    assert pi_hex_digit(2) == 3
    assert pi_hex_digit(3) == 15
