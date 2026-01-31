from digitloom.chudnovsky import chudnovsky_pi_decimal_string


PI_80 = "3.14159265358979323846264338327950288419716939937510582097494459230781640628620899"


def test_chudnovsky_pi_prefix():
    s = chudnovsky_pi_decimal_string(80, workers=1)
    assert s == PI_80
