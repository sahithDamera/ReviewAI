from io import BytesIO

import qrcode
from qrcode.image.svg import SvgPathImage


def review_qr(url: str, fmt: str) -> tuple[bytes, str, str]:
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    if fmt == "svg":
        image = qr.make_image(image_factory=SvgPathImage)
        return image.to_string(encoding="utf-8"), "image/svg+xml", "svg"
    image = qr.make_image(fill_color="black", back_color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue(), "image/png", "png"
