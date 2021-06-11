odoo.define('l10n_cl_dte_point_of_sale.ClientDetailsEdit', function (require) {
"use strict";

var ClientDetailsEdit = require('point_of_sale.ClientDetailsEdit');
var core = require('web.core');
var QWeb = core.qweb;
var _t = core._t;
var rpc = require('web.rpc');
const Registries = require('point_of_sale.Registries');


const FEClientDetailsEdit = (ClientDetailsEdit) =>
		class extends ClientDetailsEdit {
			constructor(){
				super(...arguments);
			}
			captureChange(event) {
				super.captureChange(event);
				if (['document_number', 'name'].includes(event.target.name)){
					var document_number = event.target.value || '';
					document_number = document_number.replace(/[^1234567890Kk]/g, "").toUpperCase();
					document_number = _.str.lpad(document_number, 9, '0');
					document_number = _.str.sprintf('%s.%s.%s-%s',
							document_number.slice(0, 2),
							document_number.slice(2, 5),
							document_number.slice(5, 8),
							document_number.slice(-1)
					)
					if (this.validar_rut(document_number, event.target.name === 'document_number')){
						this.props.partner.document_number = document_number;
						this.changes.document_number = document_number;
						this.get_remote_data(document_number);
					}
				}
			}

			saveChanges() {
				var self = this;
				let processedChanges = {};
				for (let [key, value] of Object.entries(this.changes)) {
						if (this.intFields.includes(key)) {
								processedChanges[key] = parseInt(value) || false;
						} else {
								processedChanges[key] = value;
						}
				}
				if ((!this.props.partner.name && !processedChanges.name) ||
						processedChanges.name === '' ){
						return this.showPopup('ErrorPopup', {
							title: _('A Customer Name Is Required'),
						});
				}
				processedChanges.id = this.props.partner.id || false;

				if (!this.props.partner.document_number && processedChanges.document_number && !this.props.partner.document_type && !processedChanges.document_type_id) {
					return this.showPopup('ErrorPopup',_t('Seleccione el tipo de documento'));
				}
				if (processedChanges.document_number ) {
					processedChanges.document_number = processedChanges.document_number.toUpperCase();
					if (!this.validar_rut(processedChanges.document_number)){
						return;
					}
				}
				if (!this.props.partner.country_id && !processedChanges.country_id) {
					return this.showPopup('ErrorPopup',_t('Seleccione el Pais'));
				}
				if (!this.props.partner.state_id && !processedChanges.state_id) {
					return this.showPopup('ErrorPopup',_t('Seleccione la Provincia'));
				}
				if (!this.props.partner.city_id && !processedChanges.city_id) {
					return this.showPopup('ErrorPopup',_t('Seleccione la comuna'));
				}
				if(!this.props.partner.street && !processedChanges.street) {
					return this.showPopup('ErrorPopup',_t('Ingrese la direccion(calle)'));
				}
				if (!this.props.partner.es_mipyme && !processedChanges.es_mipyme && (!this.props.partner.dte_email && !processedChanges.dte_email)) {
					return this.showPopup('ErrorPopup',_t('Para empresa que no es MiPyme, debe ingrear el correo dte para intercambio'));
				}
				var country = _.filter(this.env.pos.countries, function(country){ return country.id == processedChanges.country_id; });
				processedChanges.id           = partner.id || false;
				processedChanges.country_id   = processedChanges.country_id || false;
				processedChanges.barcode      = processedChanges.barcode || '';
				if (country.length > 0){
					processedChanges.vat = country[0].code + processedChanges.document_number.replace('-','').replace('.','').replace('.','');
				}
				if (processedChanges.property_product_pricelist) {
					processedChanges.property_product_pricelist = parseInt(processedChanges.property_product_pricelist, 10);
		        } else {
		        	processedChanges.property_product_pricelist = false;
		        }
				if (processedChanges.activity_description && !parseInt(processedChanges.activity_description)){
					rpc.query({
						model:'sii.activity.description',
						method:'create_from_ui',
						args: [fields]
		            }).then(function(description){
		            	processedChanges.activity_description = description;
		                rpc.query({
		                	model:'res.partner',
		                	method: 'create_from_ui',
		                	args: [fields]
		                }).then(function(partner_id){
		                  	self.saved_client_details(partner_id);
										}, function(err, ev){
											var error_body = _t('Your Internet connection is probably down.');
			                if (err.data) {
			                    var except = err.data;
			                    error_body = except.arguments && except.arguments[0] || except.message || error_body;
			                }
		              		self.gui.show_popup('error',{
		              			'title': _t('Error: Could not Save Changes partner'),
		              			'body': err_body
		              		});
		                });
		            }, function(err_type, err){
		            	if (err.data.message) {
		            		self.gui.show_popup('error',{
		            			'title': _t('Error: Could not Save Changes'),
		            			'body': err.data.message,
		            		});
		            	}else{
		            		self.gui.show_popup('error',{
		            			'title': _t('Error: Could not Save Changes'),
		            			'body': _t('Your Internet connection is probably down.'),
		            		});
		            	}
		            });
				}else{
					rpc.query({
						model: 'res.partner',
						method: 'create_from_ui',
						args: [fields]
					}).then(function(partner_id){
						self.saved_client_details(partner_id);
					}, function(err, err_type){
						if (err.data.message) {
							self.gui.show_popup('error',{
								'title': _t('Error: Could not Save Changes'),
								'body': err.data.message,
							});
						}else{
							self.gui.show_popup('error',{
								'title': _t('Error: Could not Save Changes'),
								'body': _t('Your Internet connection is probably down.'),
							});
						}
					});
				}
			this.trigger('save-changes', { processedChanges });
		}

		async get_remote_data(vat){
			var resp = await rpc.query({
				model: 'res.partner',
				method: 'get_remote_user_data',
				args: [false, vat, false]
			})
			if (resp){
				this.changes.name = resp.razon_social;
				this.props.partner.name = resp.razon_social;
				if (resp.es_mipyme){
					this.changes.es_mipyme = true;
					this.props.partner.es_mipyme = true;
				}else{
					this.changes.es_mipyme = false;
					this.props.partner.es_mipyme = false;
					this.changes.dte_email = resp.dte_email;
					this.props.partner.dte_email = resp.dte_email;
				}
			}
			this.render();
		}

		display_client_details(visibility, partner, clickpos){
				if (visibility === "edit"){
					var state_options = self.$("select[name='state_id']:visible option:not(:first)");
					var comuna_options = self.$("select[name='city_id']:visible option:not(:first)");
					self.$("select[name='country_id']").on('change', function(){
						var select = self.$("select[name='state_id']:visible");
						var selected_state = select.val();
						state_options.detach();
						var displayed_state = state_options.filter("[data-country_id="+(self.$(this).val() || 0)+"]");
						select.val(selected_state);
						displayed_state.appendTo(select).show();
					});
					self.$("select[name='city_id']").on('change', function(){
		        		var city_id = self.$(this).val() || 0;
		        		if (city_id > 0){
		        			var city = self.pos.cities_by_id[city_id];
		        			var select_country = self.$("select[name='country_id']:visible");
		        			select_country.val(city.country_id ? city.country_id[0] : 0);
		        			select_country.change();
		        			var select_state = self.$("select[name='state_id']:visible");
		        			select_state.val(city.state_id ? city.state_id[0] : 0);
		        		}
		        	});
				}
			}

			validar_rut(texto, alert=true){
				var tmpstr = "";
				var i = 0;
				for ( i=0; i < texto.length ; i++ ){
					if ( texto.charAt(i) != ' ' && texto.charAt(i) != '.' && texto.charAt(i) != '-' ){
						tmpstr = tmpstr + texto.charAt(i);
					}
				}
				texto = tmpstr;
				var largo = texto.length;
				if ( largo < 2 ){
	          if (alert){
	          	return this.showPopup('ErrorPopup',_t('Debe ingresar el rut completo'));
	          }
					return false;
				}
				for (i=0; i < largo ; i++ ){
					if ( texto.charAt(i) !="0" && texto.charAt(i) != "1" && texto.charAt(i) !="2" && texto.charAt(i) != "3" && texto.charAt(i) != "4" && texto.charAt(i) !="5" && texto.charAt(i) != "6" && texto.charAt(i) != "7" && texto.charAt(i) !="8" && texto.charAt(i) != "9" && texto.charAt(i) !="k" && texto.charAt(i) != "K" ){
					  if (alert){
					    return this.showPopup('ErrorPopup',_t('El valor ingresado no corresponde a un R.U.T valido'));
				    }
						return false;
					}
				}
				var j =0;
				var invertido = "";
				for ( i=(largo-1),j=0; i>=0; i--,j++ ){
					invertido = invertido + texto.charAt(i);
				}
				var dtexto = "";
				dtexto = dtexto + invertido.charAt(0);
				dtexto = dtexto + '-';
				var cnt = 0;

				for ( i=1, j=2; i<largo; i++,j++ ){
					// alert("i=[" + i + "] j=[" + j +"]" );
					if ( cnt == 3 ){
						dtexto = dtexto + '.';
						j++;
						dtexto = dtexto + invertido.charAt(i);
						cnt = 1;
					}else{
						dtexto = dtexto + invertido.charAt(i);
						cnt++;
					}
				}

				invertido = "";
				for ( i=(dtexto.length-1),j=0; i>=0; i--,j++ ){
					invertido = invertido + dtexto.charAt(i);
				}
				if ( this.revisarDigito2(texto, alert) ){
					return true;
				}
				return false;
			}

			revisarDigito( dvr, alert){
				var dv = dvr + ""
				if ( dv != '0' && dv != '1' && dv != '2' && dv != '3' && dv != '4' && dv != '5' && dv != '6' && dv != '7' && dv != '8' && dv != '9' && dv != 'k'  && dv != 'K'){
				        if (alert){
					     return this.showPopup('ErrorPopup',_t('Debe ingresar un digito verificador valido'));
					 }
					return false;
				}
				return true;
			}

			revisarDigito2( crut ){
				var largo = crut.length;
				if ( largo < 2 ){
					return this.showPopup('ErrorPopup',_t('Debe ingresar el rut completo'));
					return false;
				}
				if ( largo > 2 ){
					var rut = crut.substring(0, largo - 1);
				}else{
					var rut = crut.charAt(0);
				}
				var dv = crut.charAt(largo-1);
				this.revisarDigito( dv );

				if ( rut == null || dv == null ){
					return 0
				}

				var dvr = '0';
				var suma = 0;
				var mul = 2;
				var i = 0;
				for (i= rut.length -1 ; i >= 0; i--){
					suma = suma + rut.charAt(i) * mul;
					if (mul == 7){
						mul = 2;
					}else{
						mul++;
					}
				}
				var res = suma % 11;
				if (res==1){
					dvr = 'k';
				} else if (res==0){
					dvr = '0';
				} else{
					var dvi = 11-res;
					dvr = dvi + "";
				}
				if ( dvr != dv.toLowerCase()){
					return this.showPopup('ErrorPopup',_t('EL rut es incorrecto'));
					return false;
				}
				return true;
			}

		}
	Registries.Component.extend(ClientDetailsEdit, FEClientDetailsEdit);

	return FEClientDetailsEdit;
});
