"""Validate and resize uploaded cover images before storing them."""
from uuid import uuid4
from urllib.parse import urlsplit, unquote
import time

import cloudinary
import cloudinary.uploader
import cloudinary.utils
import requests
from flask import abort, current_app, send_file
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from wtforms.validators import ValidationError


def optimize_upload(max_side, keep_transparency=False):
    def validate(form, field):
        field.optimized = None
        if not field.data:
            return
        try:
            with Image.open(field.data.stream) as source:
                if source.format not in {'JPEG', 'PNG', 'WEBP'} or source.width * source.height > 25_000_000:
                    raise ValueError()
                source.thumbnail((max_side, max_side))
                image = ImageOps.exif_transpose(source).convert('RGBA' if keep_transparency else 'RGB')
                with BytesIO() as output:
                    image.save(output, 'WEBP', quality=82)
                    field.optimized = output.getvalue()
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
            raise ValidationError('Envie uma imagem JPEG, PNG ou WebP válida, com até 25 megapixels.') from exc
    return validate


def configure_photos():
    parsed = urlsplit(current_app.config.get('CLOUDINARY_URL') or '')
    if parsed.scheme != 'cloudinary' or not parsed.hostname or not parsed.username or not parsed.password:
        raise RuntimeError('CLOUDINARY_URL inválida.')
    cloudinary.config(cloud_name=parsed.hostname, api_key=unquote(parsed.username),
                      api_secret=unquote(parsed.password), secure=True)


def image_public_id(kind, reference):
    return f'easy-servicos/destaques/{kind}/{reference}'


def upload_image(kind, data):
    configure_photos()
    reference = uuid4().hex
    cloudinary.uploader.upload(BytesIO(data), public_id=image_public_id(kind, reference),
        type='authenticated', resource_type='image', format='webp', overwrite=False, timeout=30)
    return reference


def prepare_image(kind, field):
    field.reference = None
    if field.optimized is None:
        return True
    if not current_app.config.get('CLOUDINARY_URL'):
        field.errors.append('Configure o Cloudinary para enviar imagens.')
        return False
    try:
        field.reference = upload_image(kind, field.optimized)
        return True
    except Exception:
        current_app.logger.warning('Não foi possível enviar a imagem ao Cloudinary.')
        field.errors.append('Não foi possível enviar a imagem. Tente novamente.')
        return False


def save_image(obj, key, field, remove=False):
    if field.reference or remove:
        setattr(obj, key + '_data', None)
        setattr(obj, key + '_key', field.reference)


def serve_image(obj, key):
    reference = getattr(obj, key + '_key')
    if not reference:
        abort(404)
    # Old uploads remain readable until the operator transfers them.
    if len(reference) == 64:
        data = getattr(obj, key + '_data')
        if data is None:
            abort(404)
    else:
        try:
            configure_photos()
            url = cloudinary.utils.private_download_url(image_public_id(key, reference), 'webp',
                resource_type='image', type='authenticated', expires_at=int(time.time()) + 60,
                attachment=False)
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            if response.headers.get('Content-Type', '').split(';')[0] != 'image/webp':
                abort(502)
            data = response.content
        except (requests.RequestException, RuntimeError, ValueError):
            abort(502)
    return send_file(BytesIO(data), mimetype='image/webp', etag=reference)
