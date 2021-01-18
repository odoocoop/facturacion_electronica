odoo.define('l10n_cl_dte_point_of_sale.models', function (require) {
"use strict";

// implementaciónen el lado del cliente de firma
var models = require('point_of_sale.models');
var utils = require('web.utils');
var core = require('web.core');
var _t = core._t;

var modules = models.PosModel.prototype.models;
var round_pr = utils.round_precision;
var secuencias = {};

for(var i=0; i<modules.length; i++){
	var model=modules[i];
	if(model.model === 'res.company'){
		model.fields.push(
			'activity_description',
			'street',
			'city',
			'dte_resolution_date',
			'dte_resolution_number',
			'sucursal_ids',
		);
	}
	if(model.model === 'res.partner'){
		model.fields.push('document_number','activity_description','document_type_id', 'state_id', 'city_id', 'dte_email', 'sync', 'es_mipyme');
	}
	if(model.model === 'pos.session'){
		model.fields.push('caf_files', 'caf_files_exentas', 'start_number', 'start_number_exentas', 'numero_ordenes', 'numero_ordenes_exentas');
	}
	if (model.model == 'product.product') {
		model.fields.push('name');
	}
	if (model.model == 'res.country') {
		model.fields.push('code');
	}
	if (model.model == 'account.tax') {
		model.fields.push('uom_id', 'sii_code');
	}
}

models.load_models({
	model: 'res.partner',
	fields: ['document_number',],
	domain: function(self){ return [['id','=', self.company.partner_id[0]]]; },
      	loaded: function(self, dn){
      		self.company.document_number = dn[0].document_number;
      	},
});

var dcs = [];

models.load_models({
	model: 'ir.sequence',
	fields: ['id', 'sii_document_class_id'],
	domain: function(self){
						var seqs = [];
						if(self.config.secuencia_boleta){
							seqs.push(self.config.secuencia_boleta[0]);
						}
						if(self.config.secuencia_boleta_exenta){
							seqs.push(self.config.secuencia_boleta_exenta[0]);
						}
						if(self.config.secuencia_factura_afecta){
							seqs.push(self.config.secuencia_factura_afecta[0]);
						}
						if(self.config.secuencia_factura_exenta){
							seqs.push(self.config.secuencia_factura_exenta[0]);
						}
						return [['id', 'in', seqs]];
		},
		loaded: function(self, docs){
			if(docs.length > 0){
				docs.forEach(function(doc){
					dcs.push(doc.sii_document_class_id[0]);
					if (doc.id === self.config.secuencia_boleta[0]){
						self.config.secuencia_boleta = doc;
					}
					else if (doc.id === self.config.secuencia_boleta_exenta[0]){
						self.config.secuencia_boleta_exenta = doc;
					}
					else if (doc.id === self.config.secuencia_factura_afecta[0]){
						self.config.secuencia_factura_afecta = doc;
					}
					else if (doc.id === self.config.secuencia_factura_exenta[0]){
						self.config.secuencia_factura_exenta = doc;
					}
				});
				var orders = self.db.get_orders();
        for (var i = 0; i < orders.length; i++) {
        	if(orders[i].data.sequence_id === self.config.secuencia_boleta.id){
        		self.pos_session.numero_ordenes ++;
        	}else if(orders[i].data.sequence_id === self.config.secuencia_boleta_exenta.id){
        		self.pos_session.numero_ordenes_exentas ++;
        	}
        }
			}
		}
});

models.load_models({
	model: 'sii.document_class',
	fields: ['id', 'name', 'sii_code'],
	domain: function(self){ return [['id', 'in', dcs]]; },
	loaded: function(self, docs){
			if(docs.length > 0){
				docs.forEach(function(doc){
					secuencias[doc.id] = doc;
					if (self.config.secuencia_boleta && doc.id === self.config.secuencia_boleta.sii_document_class_id[0]){
						self.config.secuencia_boleta.sii_document_class_id = doc;
						self.config.secuencia_boleta.caf_files = self.pos_session.caf_files;
					}
					if (self.config.secuencia_boleta_exenta && doc.id === self.config.secuencia_boleta_exenta.sii_document_class_id[0]){
						self.config.secuencia_boleta_exenta.sii_document_class_id = doc;
						self.config.secuencia_boleta_exenta.caf_files = self.pos_session.caf_files_exentas;
					}
					if (self.config.secuencia_factura_afecta && doc.id === self.config.secuencia_factura_afecta.sii_document_class_id[0]){
						self.config.secuencia_factura_afecta.sii_document_class_id = doc;
					}
					if (self.config.secuencia_factura_exenta && doc.id === self.config.secuencia_factura_exenta.sii_document_class_id[0]){
						self.config.secuencia_factura_exenta.sii_document_class_id = doc;
					}
				})
			}
		}
});

models.load_models({
	model: 'sii.document_type',
	fields: ['id', 'name', 'sii_code'],
		loaded: function(self, dt){
			self.sii_document_types = dt;
		},
});

models.load_models({
	model: 'sii.activity.description',
	fields: ['id', 'name'],
		loaded: function(self, ad){
			self.sii_activities = ad;
		},
});

models.load_models({
	model: 'res.country.state',
	fields: ['id', 'name', 'country_id'],
		loaded: function(self, st){
			self.states = st;
		},
});

models.load_models({
	model: 'res.city',
	fields: ['id', 'name', 'state_id', 'country_id'],
		loaded: function(self, ct){
			self.cities = ct;
			self.cities_by_id = {};
            _.each(ct, function(city){
                self.cities_by_id[city.id] = city;
            });
		},
});

models.load_models({
	model: 'sii.responsability',
	fields: ['id', 'name', 'tp_sii_code'],
      	loaded: function(self, rs){
      		self.responsabilities = rs;
      	},
});


models.load_models({
	model: 'sii.sucursal',
	fields: ['id', 'name', 'sii_code', 'partner_id'],
	domain: function(self){ return [['company_id','=', self.company.id]]; },
	loaded: function(self, sucursales){
  		self.company.sucursal_ids = sucursales;
			if(sucursales ){
				_.each(sucursales, function(sucursal){
						sucursal.partner_id = self.db.get_partner_by_id(sucursal.partner_id[0]);
						if(self.config.sucursal_id  && sucursal.id === self.config.sucursal_id[0]){
							self.config.sucursal_id = sucursal;
						}
				})
			}
	},
});

var PosModelSuper = models.PosModel.prototype;
models.PosModel = models.PosModel.extend({
	folios_factura_afecta: function(){
		return (this.secuencia_factura_afecta || !this.folios_factura_exenta());
	},
	folios_factura_exenta: function(){
		return this.secuencia_factura_exenta;
	},
	folios_boleta_exenta: function(){
		return this.pos_session.caf_files_exentas;
	},
	folios_boleta_afecta: function(){
		return this.pos_session.caf_files;
	},
	get_next_number: function(sii_document_number, caf_files, start_number){
		var start_caf_file = false;
		for (var x in caf_files){
			if(parseInt(caf_files[x].AUTORIZACION.CAF.DA.RNG.D) <= parseInt(start_number)
					&& parseInt(start_number) <= parseInt(caf_files[x].AUTORIZACION.CAF.DA.RNG.H)){
				start_caf_file = caf_files[x];
			}
		}
		var caf_file = false;
		var gived = 0;
		for (var x in caf_files){
			if(parseInt(caf_files[x].AUTORIZACION.CAF.DA.RNG.D) <= sii_document_number &&
					sii_document_number >= parseInt(caf_files[x].AUTORIZACION.CAF.DA.RNG.H)){
				caf_file = caf_files[x];
			}else if( !caf_file || ( sii_document_number < parseInt(caf_files[x].AUTORIZACION.CAF.DA.RNG.D) &&
					sii_document_number < parseInt(caf_file.AUTORIZACION.CAF.DA.RNG.D) &&
					parseInt(caf_file.AUTORIZACION.CAF.DA.RNG.D) < parseInt(caf_files[x].AUTORIZACION.CAF.DA.RNG.D)
			)){// menor de los superiores caf
				caf_file = caf_files[x];
			}
			if (sii_document_number > parseInt(caf_files[x].AUTORIZACION.CAF.DA.RNG.H) && caf_files[x] != start_caf_file){
				gived += (parseInt(caf_files[x].AUTORIZACION.CAF.DA.RNG.H) - parseInt(caf_files[x].AUTORIZACION.CAF.DA.RNG.D)) +1;
			}
		}
		if (!caf_file){
			return sii_document_number;
		}
		if(sii_document_number < parseInt(caf_file.AUTORIZACION.CAF.DA.RNG.D)){
			var dif = sii_document_number - ((parseInt(start_caf_file.AUTORIZACION.CAF.DA.RNG.H) - start_number) + 1 + gived);
			sii_document_number = parseInt(caf_file.AUTORIZACION.CAF.DA.RNG.D) + dif;
			if (sii_document_number >  parseInt(caf_file.AUTORIZACION.CAF.DA.RNG.H)){
				sii_document_number = this.get_next_number(
					sii_document_number, caf_files, start_number);
			}
		}
		return sii_document_number;
	},
	push_order: function(order, opts) {
		if(order && order.es_boleta()){
			if(order.es_boleta_exenta()){
				var orden_numero = this.pos_session.numero_ordenes_exentas;
				this.pos_session.numero_ordenes_exentas ++;
			}else{
				var orden_numero = this.pos_session.numero_ordenes;
				this.pos_session.numero_ordenes ++;
			}
			order.orden_numero = orden_numero+1;
			var caf_files = JSON.parse(order.sequence_id.caf_files);
			var start_number = order.sequence_id.sii_document_class_id.sii_code == 41 ? this.pos_session.start_number_exentas : this.pos_session.start_number;

			var sii_document_number = this.get_next_number(
				orden_numero + parseInt(start_number),
				caf_files, start_number);

			order.sii_document_number = sii_document_number;
			var amount = Math.round(order.get_total_with_tax());
			if (amount > 0){
				order.signature = order.timbrar(order);
			}
	  }
		return PosModelSuper.push_order.call(this, order, opts);
	},
	get_sequence_next: function(seq){
		if (!seq){
			return 0;
		}
		var orden_numero = 0;
		if(seq.sii_document_class_id.sii_code === 41){
			orden_numero =this.pos_session.numero_ordenes_exentas;
		}else{
			orden_numero = this.pos_session.numero_ordenes;
		}
		var caf_files = JSON.parse(seq.caf_files);
		var start_number = seq.sii_document_class_id.sii_code == 41 ? this.pos_session.start_number_exentas : this.pos_session.start_number;
		return this.get_next_number(
			parseInt(orden_numero) + parseInt(start_number),
			caf_files, start_number);
	},
	get_sequence_left: function(seq){
		if (!seq){
			return 0;
		}
		var sii_document_number = this.get_sequence_next(seq);
		var caf_files = JSON.parse(seq.caf_files);
		var left = 0;
		for (var x in caf_files){
			if (sii_document_number > parseInt(caf_files[x].AUTORIZACION.CAF.DA.RNG.D)){
				var desde = sii_document_number;
			}else{
					var desde  = parseInt(caf_files[x].AUTORIZACION.CAF.DA.RNG.D);
			}
			var hasta = parseInt(caf_files[x].AUTORIZACION.CAF.DA.RNG.H);
			if(sii_document_number <= hasta){
				var dif = 0;
				if (desde < sii_document_number){
					sii_document_number - desde;
				}
				left += (hasta -desde -dif) +1;
			}
		}
		return left;
	}
});

var _super_order_line = models.Orderline.prototype;
models.Orderline = models.Orderline.extend({
	_compute_factor: function(tax, uom_id){
		var tax_uom = this.pos.units_by_id[tax.uom_id[0]];
		var amount_tax = tax.amount;
		if (tax.uom_id !== uom_id){
			var factor = (1 / tax_uom.factor);
			amount_tax = (amount_tax / factor);
		}
		return amount_tax;
	},
	_compute_all: function(tax, base_amount, quantity, uom_id) {
			if (tax.amount_type === 'fixed') {
					var amount_tax = this._compute_factor(tax, uom_id);
					var sign_base_amount = Math.sign(base_amount) || 1;
					// Since base amount has been computed with quantity
					// we take the abs of quantity
					// Same logic as bb72dea98de4dae8f59e397f232a0636411d37ce
					return amount_tax * sign_base_amount * Math.abs(quantity);
			}
			if ((tax.amount_type === 'percent' && !tax.price_include) || (tax.amount_type === 'division' && tax.price_include)){
					return base_amount * tax.amount / 100;
			}
			if (tax.amount_type === 'percent' && tax.price_include){
					return base_amount - (base_amount / (1 + tax.amount / 100));
			}
			if (tax.amount_type === 'division' && !tax.price_include) {
					return base_amount / (1 - tax.amount / 100) - base_amount;
			}
			return false;
	},
	_fix_composed_included_tax: function(taxes, base, quantity, uom_id){
        let composed_tax = {}
        var price_included = false;
        var percent = 0.0;
        var rec = 0.0;
				var self = this;
        _(taxes).each(function(tax){
            if (tax.price_include){
                price_included = true;
	            if (tax.amount_type == 'percent'){
	                percent += tax.amount;
								}
	            else{
	                var amount_tax = self._compute_factor(tax, uom_id);
	                rec += (quantity * amount_tax);
								}
						}
				});
        if (price_included){
            var _base = base - rec
            var common_base = (_base / (1 + percent / 100.0))
            _(taxes).each(function(tax){
                if (tax.amount_type == 'percent'){
                    composed_tax[tax.id] = (common_base * (1 + tax.amount / 100))
									}
								});
				}
        return composed_tax
	},
	compute_all: function(taxes, price_unit, quantity, currency_rounding, no_map_tax, uom_id) {
			var self = this;
			var list_taxes = [];
			var currency_rounding_bak = currency_rounding;
			if (this.pos.company.tax_calculation_rounding_method == "round_globally"){
				 currency_rounding = currency_rounding * 0.00001;
			}
			var total_excluded = round_pr(price_unit * quantity, currency_rounding);
			total_excluded = round_pr(total_excluded, currency_rounding_bak);
			var total_included = total_excluded;
			var base = total_excluded;
			var included = false;
			let composed_tax = {}
      if (taxes.length > 1){
          composed_tax = self._fix_composed_included_tax(taxes, total_included, quantity, uom_id)
			}
			_(taxes).each(function(tax) {
					included = tax.price_include;
					if (!no_map_tax){
							tax = self._map_tax_fiscal_position(tax);
					}
					if (!tax){
							return;
					}
					if (tax.amount_type === 'group'){
							var ret = self.compute_all(tax.children_tax_ids, price_unit, quantity, currency_rounding, false, uom_id);
							total_excluded = ret.total_excluded;
							base = ret.total_excluded;
							total_included = ret.total_included;
							list_taxes = list_taxes.concat(ret.taxes);
					}
					else {
  						var _base = tax.id in composed_tax ? composed_tax[tax.id] : base;
							var tax_amount = self._compute_all(tax, _base, quantity, uom_id);
							tax_amount = round_pr(tax_amount, currency_rounding);
							if (tax_amount){
									if (tax.price_include) {
											total_excluded -= tax_amount;
											_base -= tax_amount;
									}
									else {
											total_included += round_pr(tax_amount, currency_rounding_bak);
									}
									if (tax.include_base_amount) {
											base += tax_amount;
									}
									var data = {
											id: tax.id,
											amount: tax_amount,
											name: tax.name,
									};
									list_taxes.push(data);
							}
					}
			});
			var vals = {
					taxes: list_taxes,
					total_excluded: round_pr(total_excluded, currency_rounding_bak),
					total_included: round_pr(total_included, currency_rounding_bak),
			};
			if (included){
				vals.not_round = round_pr(total_excluded, currency_rounding);
			}
			return vals;
	},
	get_all_prices: function(){
			var price_unit = this.get_unit_price() * (1.0 - (this.get_discount() / 100.0));
			var taxtotal = 0;

			var product =  this.get_product();
			var taxes_ids = product.taxes_id;
			var taxes =  this.pos.taxes;
			var taxdetail = {};
			var product_taxes = [];

			_(taxes_ids).each(function(el){
					product_taxes.push(_.detect(taxes, function(t){
							return t.id === el;
					}));
			});

			var all_taxes = this.compute_all(product_taxes,
				price_unit, this.get_quantity(), this.pos.currency.rounding, false, this.get_unit());
			_(all_taxes.taxes).each(function(tax) {
					taxtotal += tax.amount;
					taxdetail[tax.id] = tax.amount;
			});

			var vals = {
					"priceWithTax": all_taxes.total_included,
					"priceWithoutTax": all_taxes.total_excluded,
					"tax": taxtotal,
					"taxDetails": taxdetail,
			};
			if (all_taxes.not_round){
				vals.priceNotRound = all_taxes.not_round;
			}
			return vals;
	},

});

var _super_order = models.Order.prototype;
models.Order = models.Order.extend({
	initialize: function(attr, options) {
		_super_order.initialize.call(this,attr,options);
		this.unset_boleta();
		if (this.pos.config.marcar === 'boleta' && this.pos.config.secuencia_boleta){
			this.set_boleta(true);
			this.set_tipo(this.pos.config.secuencia_boleta);
		}else if (this.pos.config.marcar === 'boleta_exenta' && this.pos.config.secuencia_boleta_exenta){
			this.set_boleta(true);
			this.set_tipo(this.pos.config.secuencia_boleta_exenta);
		}else if (this.pos.config.marcar === 'factura'){
			this.set_to_invoice(true);
			this.set_tipo(this.pos.config.secuencia_factura_afecta);
		}else if (this.pos.config.marcar === 'factura_exenta'){
			this.set_to_invoice(true);
			this.set_tipo(this.pos.config.secuencia_factura_exenta);
		}
		if(this.es_boleta()){
			this.signature = this.signature || false;
			this.sii_document_number = this.sii_document_number || false;
			this.orden_numero = this.orden_numero || this.pos.pos_session.numero_ordenes;
			if (this.orden_numero <= 0){
				this.orden_numero = 1;
			}
		}
	},
	export_as_JSON: function() {
		var json = _super_order.export_as_JSON.apply(this,arguments);
		if (this.sequence_id){
			json.sequence_id = this.sequence_id.id;
		}else{
			json.sequence_id = false;
		}
		json.sii_document_number = this.sii_document_number;
		json.signature = this.signature;
		json.orden_numero = this.orden_numero;
		json.finalized = this.finalized;
		return json;
	},
  init_from_JSON: function(json) {// carga pedido individual
  	_super_order.init_from_JSON.apply(this,arguments);
		if (json.sequence_id){
  		this.sequence_id = secuencias[json.sequence_id];
		}
  	this.sii_document_number = json.sii_document_number;
  	this.signature = json.signature;
  	this.orden_numero = json.orden_numero;
		this.finalized = json.finalized;
	},
	export_for_printing: function() {
		var self = this;
		var json = _super_order.export_for_printing.apply(this,arguments);
		json.company.document_number = this.pos.company.document_number;
		json.company.activity_description = this.pos.company.activity_description[1];
		json.company.street = this.pos.company.street;
		json.company.city = this.pos.company.city;
		json.company.dte_resolution_date = this.pos.company.dte_resolution_date;
		json.company.dte_resolution_number = this.pos.company.dte_resolution_number;
		json.sii_document_number = this.sii_document_number;
		json.orden_numero = this.orden_numero;
		if(this.sequence_id){
			json.nombre_documento = this.sequence_id.sii_document_class_id.name;
		}
		var d = self.creation_date;
		var curr_date = this.completa_cero(d.getDate());
		var curr_month = this.completa_cero(d.getMonth() + 1); // Months
																	// are zero
																	// based
		var curr_year = d.getFullYear();
		var hours = d.getHours();
		var minutes = d.getMinutes();
		var seconds = d.getSeconds();
		var date = curr_year + '-' + curr_month + '-' + curr_date + ' ' +
			this.completa_cero(hours) + ':' + this.completa_cero(minutes) + ':' + this.completa_cero(seconds);
		json.creation_date = date;
		json.barcode = this.barcode_pdf417();
		json.exento = this.get_total_exento();
		json.referencias = [];
		json.client = this.get('client');
		return json;
	},
	initialize_validation_date: function(){
		_super_order.initialize_validation_date.apply(this,arguments);
		if (!this.is_to_invoice() && this.es_boleta() && !this.finalized){
			this.finalized = true;
		}
	},
	get_total_exento:function(){
		var self = this;
		var taxes =  this.pos.taxes;
		var exento = 0;
		self.orderlines.each(function(line){
			var product =  line.get_product();
			var taxes_ids = product.taxes_id;
			_(taxes_ids).each(function(id){
					var t = self.pos.taxes_by_id[id];
					if(t.sii_code === 0){
						exento += (line.get_unit_price() * line.get_quantity());
					}
			});
		});
		return exento;
	},
	get_tax_details: function(){
			var self = this;
			var details = {};
			var fulldetails = [];
			var boleta = self.es_boleta();
			var amount_total = 0;
			var iva = false;
			self.orderlines.each(function(line){
					var exento = false;
					var ldetails = line.get_tax_details();
					for(var id in ldetails){
						if(ldetails.hasOwnProperty(id)){
							var t = self.pos.taxes_by_id[id];
							if(boleta && t.sii_code !== 0){
								if (t.sii_code  === 14 || t.sii_code  === 15 ){
									iva = t;
								}
							}else{
								if(t.sii_code === 0){
									exento = true;
								}else{
									details[id] = (details[id] || 0) + ldetails[id];
								}
							}
						}
					}
					if (boleta && !exento){
						amount_total += line.get_price_with_tax();
					}
			});
			if (iva){
				details[iva.id] = round_pr(((amount_total / (1 + (iva.amount/100)))*(iva.amount/100) ), 0);
			}
			for(var id in details){
					if(details.hasOwnProperty(id)){
							fulldetails.push({amount: details[id], tax: self.pos.taxes_by_id[id], name: self.pos.taxes_by_id[id].name});
					}
			}
			return fulldetails;
	},
	get_total_tax: function() {
		var self = this;
		var tax = 0;
		var tDetails = self.get_tax_details();
		tDetails.forEach(function(t) {
			tax += round_pr(t.amount, self.pos.currency.rounding);
		});
		return tax;
	},
	get_total_without_tax: function() {
			var self = this;
			if(self.es_boleta()){
				var neto = 0;
				var amount_total = 0;
				var iva = false;
				self.orderlines.each(function(line){
						var exento = false;
						var ldetails = line.get_tax_details();
						for(var id in ldetails){
							var t = self.pos.taxes_by_id[id];
							if(t.sii_code !== 0){
								if (t.sii_code  === 14 || t.sii_code  === 15 ){
									iva = t;
								}
							}else{
								exento = true;
								var all_prices = line.get_all_prices();
								var price = all_prices.priceNotRound || all_prices.priceWithoutTax;
								neto += price;
							}
						}
						if (self.es_boleta() && !exento){
							amount_total += line.get_price_with_tax();
						}
				});
				if (iva){
					neto += round_pr((amount_total / (1 + (iva.amount/100))), self.pos.currency.rounding);
				}
				return neto;
			}
			return round_pr(this.orderlines.reduce((function(sum, orderLine) {
					var all_prices = orderLine.get_all_prices();
					var price = all_prices.priceNotRound || all_prices.priceWithoutTax;
					return sum + price;
			}), 0), this.pos.currency.rounding);
	},
	fix_tax_included_price: function(line){
			if(this.fiscal_position){
					var unit_price = line.price;
					var taxes = line.get_taxes();
					var mapped_included_taxes = [];
					var uom_id = false;
					_(taxes).each(function(tax) {
							var line_tax = line._map_tax_fiscal_position(tax);
							if(tax.price_include && tax.id != line_tax.id){
								  uom_id = line.get_unit();
									mapped_included_taxes.push(tax);
							}
					})

					if (mapped_included_taxes.length > 0) {
							unit_price = line.compute_all(mapped_included_taxes, unit_price, 1, this.pos.currency.rounding, true, uom_id).total_excluded;
					}

					line.set_unit_price(unit_price);
			}
	},
	set_tipo: function(tipo){
		this.sequence_id = tipo;
	},
	set_boleta: function(boleta){
		this.boleta = boleta;
	},
	unset_tipo: function(){
		this.sequence_id = false;
	},
	unset_boleta: function(){
		this.set_tipo(false);
		this.set_boleta(false);
		this.orden_numero = false;
		this.sii_document_number = false;
		this.unset_tipo();
	},
    // esto devolvera True si es Boleta(independiente si es exenta o afecta)
    // para diferenciar solo si es una factura o una boleta
	es_boleta: function(){
		return this.boleta;
	},
    // esto devolvera True si es Boleta exenta(sii_code = 41)
	es_boleta_exenta: function(check_marcar=false){
		if(!this.es_boleta()){
			return false;
		}
		return (this.sequence_id.sii_document_class_id.sii_code === 41);
  },
    // esto devolvera True si es Boleta afecta(sii_code = 39)
	es_boleta_afecta: function(check_marcar=false){
		if(!this.es_boleta()){
			return false;
		}
		return (this.sequence_id.sii_document_class_id.sii_code === 39);
	},
	es_factura_afecta: function(){
		return (this.sequence_id && this.sequence_id.sii_document_class_id.sii_code === 33 && this.is_to_invoice());
	},
	es_factura_exenta: function(){
		return (this.sequence_id && this.sequence_id.sii_document_class_id.sii_code === 34 && this.is_to_invoice());
	},
	crear_guia: function(){
		return (this.pos.config.dte_picking && (this.pos.config.dte_picking_option === 'all' || (this.pos.config.dte_picking_option === 'no_tributarios' && !this.es_tributaria())));
	},
	es_tributaria: function(){
		if (this.es_boleta()){
			return this.es_boleta();
		}
		if (this.is_to_invoice()){
			if (this.pos.config.secuencia_factura_afecta){
				return true;
			}
			return (this.es_factura_exenta() && this.pos.config.secuencia_factura_exenta);
		}
		return false;
	},
	completa_cero: function(val){
    	if (parseInt(val) < 10){
    		return '0' + val;
    	}
    	return val;
    },
	timbrar: function(order){
		if (order.signature){ // no firmar otra vez
			return order.signature;
		}
		var caf_files = JSON.parse(order.sequence_id.caf_files);
		var caf_file = false;
		for (var x in caf_files){
			if(caf_files[x].AUTORIZACION.CAF.DA.RNG.D <= order.sii_document_number && order.sii_document_number <= caf_files[x].AUTORIZACION.CAF.DA.RNG.H){
				caf_file =caf_files[x]
			}
		}
		if (!caf_file){
			this.pos.gui.show_popup('error',_t('No quedan más Folios Disponibles'));
			return false;
		}
		var priv_key = caf_file.AUTORIZACION.RSASK;
		var pki = forge.pki;
		var privateKey = pki.privateKeyFromPem(priv_key);
		var md = forge.md.sha1.create();
		var partner_id = this.get_client();
		if(!partner_id){
			partner_id = {};
			partner_id.name = "Usuario Anonimo";
		}
		if(!partner_id.document_number){
			partner_id.document_number = "66666666-6";
		}
		function format_str(text){
			return text.replace('&', '&amp;');
		}
		var product_name = false;
		var ols = order.orderlines.models;
		var ols2 = ols;
		for (var p in ols){
			var es_menor = true;
			for(var i in ols2){
				if(ols[p].id !== ols2[i].id && ols[p].id > ols2[i].id){
					es_menor = false;
				}
				if(es_menor === true){
					product_name = format_str(ols[p].product.name);
				}
			}
		}
		var d = order.validation_date;
		var curr_date = this.completa_cero(d.getDate());
		var curr_month = this.completa_cero(d.getMonth() + 1); // Months
																// are zero
																// based
		var curr_year = d.getFullYear();
		var hours = d.getHours();
		var minutes = d.getMinutes();
		var seconds = d.getSeconds();
		var date = curr_year + '-' + curr_month + '-' + curr_date + 'T' +
			this.completa_cero(hours) + ':' + this.completa_cero(minutes) + ':' + this.completa_cero(seconds);
		var rut_emisor = this.pos.company.document_number.replace('.','').replace('.','');
		if (rut_emisor.charAt(0) == "0"){
			rut_emisor = rut_emisor.substr(1);
		}
		var string='<DD>' +
			'<RE>' + rut_emisor + '</RE>' +
			'<TD>' + order.sequence_id.sii_document_class_id.sii_code + '</TD>' +
			'<F>' + order.sii_document_number + '</F>' +
			'<FE>' + curr_year + '-' + curr_month + '-' + curr_date + '</FE>' +
			'<RR>' + partner_id.document_number.replace('.','').replace('.','') +'</RR>' +
			'<RSR>' + format_str(partner_id.name) + '</RSR>' +
			'<MNT>' + Math.round(this.get_total_with_tax()) + '</MNT>' +
			'<IT1>' + product_name + '</IT1>' +
			'<CAF version="1.0"><DA><RE>' + caf_file.AUTORIZACION.CAF.DA.RE + '</RE>' +
				'<RS>' + format_str(caf_file.AUTORIZACION.CAF.DA.RS) + '</RS>' +
				'<TD>' + caf_file.AUTORIZACION.CAF.DA.TD + '</TD>' +
				'<RNG><D>' + caf_file.AUTORIZACION.CAF.DA.RNG.D + '</D><H>' + caf_file.AUTORIZACION.CAF.DA.RNG.H + '</H></RNG>' +
				'<FA>' + caf_file.AUTORIZACION.CAF.DA.FA + '</FA>' +
				'<RSAPK><M>' + caf_file.AUTORIZACION.CAF.DA.RSAPK.M + '</M><E>' + caf_file.AUTORIZACION.CAF.DA.RSAPK.E + '</E></RSAPK>' +
				'<IDK>' + caf_file.AUTORIZACION.CAF.DA.IDK + '</IDK>' +
				'</DA>' +
				'<FRMA algoritmo="SHA1withRSA">' + caf_file.AUTORIZACION.CAF.FRMA + '</FRMA>' +
			'</CAF>'+
			'<TSTED>' + date + '</TSTED></DD>';
		md.update(string);
		var signature = forge.util.encode64(privateKey.sign(md));
		string = '<TED version="1.0">' + string + '<FRMT algoritmo="SHA1withRSA">' + signature + '</FRMT></TED>';
		return string;
	},
    barcode_pdf417: function(){
    	var order = this.pos.get_order();
    	if (!order.sequence_id || !order.sii_document_number){
    		return false;
    	}
    	PDF417.ROWHEIGHT = 2;
    	PDF417.init(order.signature, 6);
    	var barcode = PDF417.getBarcodeArray();
    	var bw = 2;
    	var bh = 2;
    	var canvas = document.createElement('canvas');
    	canvas.width = bw * barcode['num_cols'];
    	canvas.height = 255;
    	var ctx = canvas.getContext('2d');
    	var y = 0;
    	for (var r = 0; r < barcode['num_rows']; ++r) {
    		var x = 0;
    		for (var c = 0; c < barcode['num_cols']; ++c) {
    			if (barcode['bcode'][r][c] == 1) {
    				ctx.fillRect(x, y, bw, bh);
    			}
    			x += bw;
    		}
    		y += bh;
    	}
    	return canvas.toDataURL("image/png");
	},
});

});
