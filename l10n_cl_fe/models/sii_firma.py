# -*- coding: utf-8 -*-
from datetime import datetime
from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import UserError
from datetime import datetime, date
import dateutil.relativedelta as relativedelta
import base64
import logging
_logger = logging.getLogger(__name__)
try:
    from OpenSSL import crypto
    type_ = crypto.FILETYPE_PEM
except ImportError:
    _logger.warning('Error en cargar crypto')
try:
    from facturacion_electronica.firma import Firma
except:
    _logger.warning("Problema a cargar facturacion_electronica")

class SignatureCert(models.Model):
    _name = 'sii.firma'

    def alerta_vencimiento(self):
        expiration = datetime.strptime(self.expire_date, '%Y-%m-%d')
        if expiration < (datetime.now() + relativedelta.relativedelta(days=30)):
            alert_msg = 'Firma pronto a vencer'
            self.env['bus.bus'].sendone((self._cr.dbname,
                                    'sii.firma',
                                    self.env.user.partner_id.id),
                                    {
                                        'title': "Alerta sobre Firma Electrónica",
                                        'message': alert_msg,
                                        'type': 'dte_notif',
                                    })

    def check_signature(self):
        for s in self.sudo():
            if s.state not in ['valid', 'unverified']:
                continue
            expired = datetime.strptime(s.expire_date, '%Y-%m-%d') < datetime.now()
            state = 'expired' if expired else 'valid'
            if s.state != state:
                s.state = state
                s.active = not expired

    @api.onchange('subject_serial_number')
    def set_state(self):
        if self.subject_serial_number:
            rut = self.subject_serial_number.replace('.', '').upper()
            if not self.env.user.partner_id.check_vat_cl(rut.replace('-', '')):
                raise UserError(_('Not Valid Subject Serial Number'))
            self.subject_serial_number = rut
            self.check_signature()
        elif self.file_content:
            self.state = 'incomplete'

    name = fields.Char(
            string='File Name',
            required=True,
    )
    file_content = fields.Binary(
        string='Signature File',
        help='Upload the Signature File',
    )
    password = fields.Char(
            string='Password',
    )
    emision_date = fields.Date(
        string='Emision Date',
        help='Not Before this Date',
        readonly=True,
    )
    expire_date = fields.Date(
        string='Expire Date',
        help='Not After this Date',
        readonly=True,
    )
    state = fields.Selection(
        [
            ('unverified', 'Unverified'),
            ('incomplete', 'Incomplete'),
            ('valid', 'Valid'),
            ('expired', 'Expired')
        ],
        string='state',
        default='unverified',
        help='''Draft: means it has not been checked yet.\nYou must press the\
"check" button.''',
    )
    subject_title = fields.Char(string='Subject Title', readonly=True)
    subject_c = fields.Char(string='Subject Country', readonly=True)
    subject_serial_number = fields.Char(
        string='Subject Serial Number',
        readonly=True,
        states={'draft': [('readonly', False)],
                'incomplete': [('readonly', False)],
                'unverified': [('readonly', False)]})
    subject_common_name = fields.Char(
        string='Subject Common Name', readonly=True)
    subject_email_address = fields.Char(
        string='Subject Email Address', readonly=True)
    issuer_country = fields.Char(string='Issuer Country', readonly=True)
    issuer_serial_number = fields.Char(
        string='Issuer Serial Number', readonly=True)
    issuer_common_name = fields.Char(
        string='Issuer Common Name', readonly=True)
    issuer_email_address = fields.Char(
        string='Issuer Email Address', readonly=True)
    issuer_organization = fields.Char(
        string='Issuer Organization', readonly=True)
    cert_serial_number = fields.Char(string='Serial Number', readonly=True)
    cert_signature_algor = fields.Char(string='Signature Algorithm', readonly=True)
    cert_version = fields.Char(string='Version', readonly=True)
    cert_hash = fields.Char(string='Hash', readonly=True)
    private_key_bits = fields.Char(string='Private Key Bits', readonly=True)
    private_key_check = fields.Char(string='Private Key Check', readonly=True)
    private_key_type = fields.Char(string='Private Key Type', readonly=True)
    cert = fields.Text(string='Certificate', readonly=True)
    priv_key = fields.Text(string='Private Key', readonly=True)
    user_ids = fields.Many2many(
            'res.users',
            string='Authorized Users',
            default=lambda self: [self.env.uid],
    )
    company_ids = fields.Many2many(
        'res.company',
        string='Authorized Companies',
        default=lambda self: [self.env.user.company_id.id],
        required=True,
    )
    priority = fields.Integer(
        string="Priority",
        default=1,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
    )

    _sql_constraints = [('name', 'unique(name, subject_serial_number, active)', 'Name must be unique!'), ]
    _order = 'priority DESC'

    @api.multi
    def action_process(self):
        filecontent = base64.b64decode(self.file_content)
        try:
            p12 = crypto.load_pkcs12(filecontent, self.password)
        except:
            raise UserError('Error al abrir la firma, posiblmente ha ingresado\
 mal la clave de la firma o el archivo no es compatible.')

        cert = p12.get_certificate()
        privky = p12.get_privatekey()
        cacert = p12.get_ca_certificates()
        issuer = cert.get_issuer()
        subject = cert.get_subject()

        self.write({
            'emision_date': datetime.strptime(cert.get_notBefore().decode("utf-8"), '%Y%m%d%H%M%SZ'),
            'expire_date': datetime.strptime(cert.get_notAfter().decode("utf-8"), '%Y%m%d%H%M%SZ'),
            'subject_c': subject.C,
            'subject_title': subject.title,
            'subject_common_name': subject.CN,
            'subject_serial_number': subject.serialNumber,
            'subject_email_address': subject.emailAddress,
            'issuer_country': issuer.C,
            'issuer_organization': issuer.O,
            'issuer_common_name': issuer.CN,
            'issuer_serial_number': issuer.serialNumber,
            'issuer_email_address': issuer.emailAddress,
            'cert_serial_number': cert.get_serial_number(),
            'cert_signature_algor': cert.get_signature_algorithm(),
            'cert_version': cert.get_version(),
            'cert_hash': cert.subject_name_hash(),
            'private_key_bits': privky.bits(),
            'private_key_check': privky.check(),
            'private_key_type': privky.type(),
            'priv_key': crypto.dump_privatekey(type_, p12.get_privatekey()),
            'cert': crypto.dump_certificate(type_, p12.get_certificate()),
            'password': False,
        })
        self.set_state()

    def firmar(self, string, uri=False, type="doc"):
        firma = Firma({
                'priv_key': self.priv_key,
                'cert': self.cert,
                'rut_firmante': self.subject_serial_number,
                'init_signature': False
            })
        return firma.firmar(string=string, uri=uri, type=type)

    def generar_firma(self, ddxml, privkey=False):
        if not privkey:
            privkey = self.priv_key
        firma = Firma({
                'priv_key': privkey,
                'cert': self.cert,
                'rut_firmante': self.subject_serial_number,
                'init_signature': False
            })
        return firma.generar_firma(texto=ddxml.decode())
