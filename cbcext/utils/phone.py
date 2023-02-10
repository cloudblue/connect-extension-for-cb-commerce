import re

from phonenumbers import is_valid_number, NumberParseException, parse as phone_parse

from cbcext.services.exceptions import InvalidPhoneException


def substitute_plus(telephone):
    if telephone and telephone[0] != "+":
        telephone = "+{telephone}".format(telephone=telephone)

    return telephone


def _correct_phone_str(phone_str):
    phone_str = substitute_plus(phone_str)

    if '#' not in phone_str:
        phone_number = phone_parse(phone_str)
        return '+{country_code}##{number}#'.format(
            country_code=phone_number.country_code,
            number=phone_number.national_number,
        )

    return phone_str


def parse_phone_number(phone_str):
    if not phone_str:
        return None

    phone_str = _correct_phone_str(phone_str)
    return dict(
        zip(
            (
                'country_code',
                'area_code',
                'phone_number',
                'extension',
            ),
            phone_str.split('#'),
        ),
    )


TELEPHONE_RE = re.compile(r"^(\d*#){3}(\d*)$")


def validate_phone_number(value):
    if not re.match(TELEPHONE_RE, value):

        try:
            value = substitute_plus(value)

            phone_obj = phone_parse(value)
            if not is_valid_number(phone_obj):
                raise InvalidPhoneException(value)

        except NumberParseException:
            raise InvalidPhoneException(value)
