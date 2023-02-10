import os

from starlette.responses import FileResponse


def download_hub_aps_package():
    file_location = os.path.join(
        os.path.dirname(__file__),
        'aps_package/CloudBlue-Connect-Extension.app.zip',
    )
    return FileResponse(
        file_location,
        media_type='application/octet-stream',
        filename='CloudBlue-Connect-Extension.app.zip',
    )
