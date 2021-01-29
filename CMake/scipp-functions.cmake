include(scipp-util)

scipp_unary(math abs)
scipp_unary(math exp)
scipp_unary(math log)
scipp_unary(math log10)
scipp_unary(math reciprocal)
scipp_unary(math sqrt)
setup_scipp_category(math)

scipp_unary(util values SKIP_VARIABLE NO_OUT)
scipp_unary(util variances SKIP_VARIABLE NO_OUT)
setup_scipp_category(util)

scipp_unary(trigonometry sin SKIP_VARIABLE)
scipp_unary(trigonometry cos SKIP_VARIABLE)
scipp_unary(trigonometry tan SKIP_VARIABLE)
scipp_unary(trigonometry asin SKIP_VARIABLE)
scipp_unary(trigonometry acos SKIP_VARIABLE)
scipp_unary(trigonometry atan SKIP_VARIABLE)
setup_scipp_category(trigonometry)

scipp_binary(comparison equal)
scipp_binary(comparison greater)
scipp_binary(comparison greater_equal)
scipp_binary(comparison less)
scipp_binary(comparison less_equal)
scipp_binary(comparison not_equal)
setup_scipp_category(comparison)
