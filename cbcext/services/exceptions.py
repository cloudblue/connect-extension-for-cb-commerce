class CBCException(Exception):
    pass


class InvalidPhoneException(CBCException):

    TELEPHONE_ERROR_MSG_TMPL = (
        "Invalid telephone format. "
        'Expected format: "7#999#999#9999", "79999999999" or "+79999999999 ext. 0". Passed "{val}"'
    )

    def __init__(self, passed_value):
        self.passed_value = passed_value

    def __str__(self):
        return self.TELEPHONE_ERROR_MSG_TMPL.format(val=self.passed_value)


class TokenException(Exception):
    """
    Exception to denote that We can't get APS token for given user, maybe due temp failure"""
