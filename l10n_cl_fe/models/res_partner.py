# -*- encoding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from odoo.tools.translate import _
import re
import json
import logging
_logger = logging.getLogger(__name__)
try:
    import urllib3
    urllib3.disable_warnings()
    pool = urllib3.PoolManager()
except:
    _logger.warning("no se ha cargado urllib3")


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _get_default_tp_type(self):
        try:
            return self.env.ref('l10n_cl_fe.res_IVARI')
        except:
            return self.env['sii.responsability']

    def _get_default_doc_type(self):
        try:
            return self.env.ref('l10n_cl_fe.dt_RUT')
        except:
            return self.env['sii.document_type']

    @api.model
    def _get_default_country(self):
        return self.env.user.company_id.country_id.id or self.env.user.partner_id.country_id.id

    @api.depends('child_ids')
    def _compute_dte_email(self):
        for p in self:
            if p.dte_email == p.email:
                continue
            for dte in p.child_ids:
                if dte.type == 'dte' and dte.principal:
                    p.dte_email_id = dte.id
                    p.dte_email = dte.email
                    break
    type = fields.Selection(
        selection_add=[
            ('dte', 'Contacto DTE'),
        ]
    )
    state_id = fields.Many2one(
            "res.country.state",
            'Ubication',
        )
    responsability_id = fields.Many2one(
        'sii.responsability',
        string='Responsability',
        default=lambda self: self._get_default_tp_type(),
    )
    document_type_id = fields.Many2one(
        'sii.document_type',
        string='Document type',
        default=lambda self: self._get_default_doc_type(),
    )
    document_number = fields.Char(
        string='Document number',
        size=64,
    )
    start_date = fields.Date(
        string='Start-up Date',
    )
    tp_sii_code = fields.Char(
        'Tax Payer SII Code',
        compute='_get_tp_sii_code',
        readonly=True,
    )
    activity_description = fields.Many2one(
            'sii.activity.description',
            string='Glosa Giro', ondelete="restrict",
        )
    dte_email_id = fields.Many2one(
            'res.partner',
            string='DTE Email Principal',
            compute='_compute_dte_email',
        )
    dte_email = fields.Char(
            string='DTE Email',
            #related='dte_email_id.name',
        )
    principal = fields.Boolean(
        string="Principal DTE",
        default=lambda self: self.verify_principal(),
    )
    send_dte = fields.Boolean(
        string="Auto Enviar DTE",
        default=True,
    )
    acteco_ids = fields.Many2many(
        'partner.activities',
        string='Activities Names',
    )
    sync = fields.Boolean(
        string="syncred",
        default=False,
    )
    last_sync_update = fields.Datetime(
        string="Fecha Actualizado",
    )

    def write(self, vals):
        result = super(ResPartner, self).write(vals)
        if not vals.get('sync', False):
            for k in vals.keys():
                if k in ('name', 'dte_email', 'street', 'email', 'acteco_ids', 'website'):
                    try:
                        for r in self:
                            if r.sync and r.document_number \
                                and not r.parent_id \
                                and self.check_vat_cl(
                                    r.document_number.replace('.', '')\
                                    .replace('-', '')):
                                r.put_remote_user_data()
                    except Exception as e:
                        _logger.warning("Error en subida información %s" % str(e))
                    break
        return result

    @api.onchange('dte_email')
    def set_temporal_email_cambiar_a_related(self):
        ''' Esto eliminar en la versión siguiente, es solamente para evitar
            problemas al actualizar '''
        if not self.is_company and not self.dte_email or\
            (not self.email and not self.dte_email):
            if self.dte_email_id:
                self.dte_email_id.unlink()
            return
        if self.dte_email == self.email:
            self.send_dte = True
            self.principal = True
            return
        if not self.dte_email_id:
            partners = []
            for rec in self.child_ids:
                partners.append((4, rec.id, False))
            partners.append((0, 0,
                            {
                                'type': 'dte',
                                'name': self.dte_email,
                                'email': self.dte_email,
                                'send_dte': True,
                                'principal': True,
                            })
                        )
            self.child_ids = partners
        elif self.dte_email_id and self.dte_email_id.email != self.dte_email:
            __name = self.dte_email_id.name
            if __name == self.dte_email_id.email:
                __name = self.dte_email
            self.dte_email_id.name = __name
            self.dte_email_id.email = self.dte_email
        else:
            for r in self.child_ids:
                if r.type == 'dte':
                    r.email = self.dte_email
                    r.name = self.dte_email

    @api.onchange('principal')
    def verify_principal(self):
        another = False
        if self.type != 'dte':
            return another
        check_id = self.id
        if self.parent_id:
            check_id = self.parent_id.id
        another = self.env['res.partner'].search([
                    ('parent_id', '=', check_id),
                    ('principal', '=', True)])
        if another:
            raise UserError(_('Existe otro correo establecido como Principal'))
        return True

    #def create(self, vals):
    #    partner = super(ResPartner, self).create(vals)
    #    if vals.get('dte_email'):
    #        dte_email_id = self.env['res.partner'].create(
    #                              {
    #                                  'parent_id': self.id,
    #                                  'type': 'dte',
    #                                  'name': self.dte_email,
    #                                  'email': self.dte_email,
    #                                  'send_dte': True,
    #                                  'principal': True,
    #                              })
    #        self.dte_email_id = dte_email_id.id

    @api.multi
    @api.onchange('responsability_id')
    def _get_tp_sii_code(self):
        for record in self:
            record.tp_sii_code = str(record.responsability_id.tp_sii_code)

    @api.onchange('document_number', 'document_type_id')
    def onchange_document(self):
        mod_obj = self.env['ir.model.data']
        if self.document_number and ((
            'sii.document_type',
            self.document_type_id.id) == mod_obj.get_object_reference(
                'l10n_cl_fe', 'dt_RUT') or ('sii.document_type',
                self.document_type_id.id) == mod_obj.get_object_reference(
                    'l10n_cl_fe', 'dt_RUN')):
            document_number = (
                re.sub('[^1234567890Kk]', '', str(
                    self.document_number))).zfill(9).upper()
            if not self.check_vat_cl(document_number):
                return {'warning': {'title': _('Rut Erróneo'),
                                    'message': _('Rut Erróneo'),
                                    }
                        }
            vat = 'CL%s' % document_number
            exist = self.env['res.partner'].search(
                [
                    ('vat', '=', vat),
                    ('vat', '!=',  'CL555555555'),
                    ('commercial_partner_id', '!=', self.commercial_partner_id.id ),
                ],
                limit=1,
            )
            if exist:
                self.vat = ''
                self.document_number = ''
                return {'warning': {'title': 'Informacion para el Usuario',
                                    'message': _("El usuario %s está utilizando este documento" ) % exist.name,
                                    }}
            self.vat = vat
            self.document_number = '%s.%s.%s-%s' % (
                                        document_number[0:2], document_number[2:5],
                                        document_number[5:8], document_number[-1],
                                    )
        elif self.document_number and (
            'sii.document_type',
            self.document_type_id.id) == mod_obj.get_object_reference(
                'l10n_cl_fe',
                'dt_Sigd',
            ):
            self.document_number = ''
        else:
            self.vat = ''
        self.fill_partner()

    @api.onchange('city_id')
    def _onchange_city_id(self):
        if self.city_id:
            self.country_id = self.city_id.state_id.country_id.id
            self.state_id = self.city_id.state_id.id
            self.city = self.city_id.name

    @api.constrains('vat', 'commercial_partner_id')
    def _rut_unique(self):
        for r in self:
            if not r.vat or r.parent_id:
                continue
            partner = self.env['res.partner'].search(
                [
                    ('vat', '=', r.vat),
                    ('id', '!=', r.id),
                    ('commercial_partner_id', '!=', r.commercial_partner_id.id),
                ])
            if r.vat != "CL555555555" and partner:
                raise UserError(_('El rut: %s debe ser único') % r.vat)
                return False

    def check_vat_cl(self, vat):
        body, vdig = '', ''
        if len(vat) != 9:
            return False
        else:
            body, vdig = vat[:-1], vat[-1].upper()
        try:
            vali = list(range(2,8)) + [2,3]
            operar = '0123456789K0'[11 - (
                sum([int(digit)*factor for digit, factor in zip(
                    body[::-1],vali)]) % 11)]
            if operar == vdig:
                return True
            else:
                return False
        except IndexError:
            return False

    def _process_data(self, data={}):
        if data.get('razon_social'):
            self.name = data['razon_social']
        if data.get('dte_email') and data['dte_email'].lower() not in ['facturacionmipyme2@sii.cl', 'facturacionmipyme@sii.cl']:
            self.dte_email = data['dte_email']
        if data.get('email'):
            self.name = data['email']
        if data.get('telefono'):
            self.name = data['phone']
        if data.get('direccion'):
            self.street = data['direccion']
        if data.get('actecos'):
            for a in data['actecos']:
                ac = self.env['sii.document_class'].search([('code', '=', a)])
                self.acteco_ids += ac
        if data.get('glosa_giro'):
            query = [('name', '=', data.get('glosa_giro'))]
            ad = self.env['sii.activity.description'].search(query)
            if not ad:
                ad = self.env['sii.activity.description'].create({
                    'name': data.get('glosa_giro')
                })
            self.activity_description = ad.id
        if data.get('url'):
            self.website = data['url']
        if data.get('logo'):
            self.image = data['logo']
        self.sync = True
        if not self.document_number:
            self.document_number = data['rut']
        self.last_sync_update = data['actualizado']

    def put_remote_user_data(self):
        ICPSudo = self.env['ir.config_parameter'].sudo()
        url = ICPSudo.get_param('partner.url_remote_partners')
        token = ICPSudo.get_param('partner.token_remote_partners')
        sync = ICPSudo.get_param('partner.sync_remote_partners')
        if not url or not token or not sync:
            return
        if self.document_number in [False, 0, '0']:
            return
        try:
            resp = pool.request(
                'PUT',
                url,
                body=json.dumps(
                    {
                        'rut': self.document_number,
                        'token': token,
                        'glosa_giro': self.activity_description.name,
                        'razon_social': self.name,
                        'dte_email': self.dte_email,
                        'email': self.email,
                        'direccion': self.street,
                        #'comuna': self.
                        'telefono': self.phone,
                        'actectos': [ac.code for ac in self.acteco_ids],
                        'url': self.website,
                        'origen': ICPSudo.get_param('web.base.url'),
                        'logo': self.image.decode() if self.image else False,
                    }
                ).encode('utf-8'),
                headers={'Content-Type': 'application/json'})
            if resp.status != 200:
                _logger.warning("Error en conexión al sincronizar partners %s" % resp.data)
                message = ''
                if resp.status == 403:
                    data = json.loads(resp.data.decode('ISO-8859-1'))
                    message = data['message']
                else:
                    message = str(resp.data)
                self.env['bus.bus'].sendone((self._cr.dbname, 'res.partner', self.env.user.partner_id.id),{
                    'title': "Error en conexión al sincronizar partners",
                    'message': message,
                    'url': 'res_config',
                    'type': 'dte_notif',
                })
                return
            data = json.loads(resp.data.decode('ISO-8859-1'))
        except:
            pass

    def get_remote_user_data(self, to_check, process_data=True):
        ICPSudo = self.env['ir.config_parameter'].sudo()
        url = ICPSudo.get_param('partner.url_remote_partners')
        token = ICPSudo.get_param('partner.token_remote_partners')
        if not url or not token:
            return
        if self.document_number in [False, 0, '0']:
            return
        try:
            resp = pool.request('POST',
                                url,
                                body=json.dumps(
                                                    {
                                                        'rut': to_check,
                                                        'token': token,
                                                    }
                                                ).encode('utf-8'),
                                headers={'Content-Type': 'application/json'})
            if resp.status != 200:
                _logger.warning("Error en conexión al obtener partners %s" % resp.data)
                message = ''
                if resp.status == 403:
                    data = json.loads(resp.data.decode('ISO-8859-1'))
                    message = data['message']
                else:
                    message = str(resp.data)
                self.env['bus.bus'].sendone((self._cr.dbname, 'res.partner', self.env.user.partner_id.id),{
                    'title': "Error en conexión al obtener partners",
                    'message': message,
                    'url': 'res_config',
                    'type': 'dte_notif',
                })
                return
            data = json.loads(resp.data.decode('ISO-8859-1'))
            if not process_data:
                return data
            if not data:
                self.sync = False
                return
            self._process_data(data)
        except:
            pass

    @api.onchange('name')
    def fill_partner(self):
        if self.sync:
            return
        if self.document_number and self.check_vat_cl(self.document_number.replace('.', '').replace('-', '')):
            self.get_remote_user_data(self.document_number)
        elif self.name and self.check_vat_cl(self.name.replace('.', '').replace('-', '')):
            self.get_remote_user_data(self.name)

    @api.model
    def _check_need_update(self):
        ICPSudo = self.env['ir.config_parameter'].sudo()
        url = ICPSudo.get_param('partner.url_remote_partners')
        token = ICPSudo.get_param('partner.token_remote_partners')
        if not url or not token:
            return
        for r in self.search([('document_number', 'not in', [False, 0]), ('parent_id', '=', False)]):
            if ICPSudo.get_param('partner.sync_remote_partners'):
                r.put_remote_user_data()
            try:
                resp = pool.request('GET',
                                        url,
                                        {
                                            'rut': r.document_number,
                                            'token': token,
                                            'actualizado': r.last_sync_update,
                                        })
                if resp.status != 200:
                    _logger.warning("Error en conexión al consultar partners %s" % resp.data)
                    message = ''
                    if resp.status == 403:
                        data = json.loads(resp.data.decode('ISO-8859-1'))
                        message = data['message']
                    else:
                        message = str(resp.data)
                    self.env['bus.bus'].sendone((self._cr.dbname, 'res.partner', self.env.user.partner_id.id),{
                        'title': "Error en conexión al consultar partners",
                        'message': message,
                        'url': 'res_config',
                        'type': 'dte_notif',
                    })
                    return
                data = json.loads(resp.data.decode('ISO-8859-1'))
                if data.get('result', False):
                    r.sync = False
                    r.fill_partner()
            except:
                pass


