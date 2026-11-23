"""故意违规：低层 ``core`` import 高层 ``upper``。"""

from violation_app.upper import helper

VALUE = helper() + 1
