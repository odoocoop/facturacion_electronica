odoo.define('l10n_cl_dte_point_of_sale.PaymentScreen', function (require) {
"use strict";

  var PaymentScreen = require('point_of_sale.PaymentScreen');
  var core = require('web.core');
  var QWeb = core.qweb;
  var _t = core._t;
  var rpc = require('web.rpc');
  const Registries = require('point_of_sale.Registries');

  const FEPaymentScreen = (PaymentScreen) =>
      class extends PaymentScreen {
      	async _isOrderValid(isForceValidate) {
      		var res = super._isOrderValid(...arguments);
      		if (this.currentOrder.is_to_invoice() || this.currentOrder.es_boleta()){
                  var total_tax = this.currentOrder.get_total_tax();
                  if ((this.currentOrder.es_boleta_exenta() || this.currentOrder.es_factura_exenta()) && total_tax > 0){
            		        this.showPopup('ErrorPopup',{
            		        	'title': "Error de integridad",
            		        	'body': "No pueden haber productos afectos en boleta/factura exenta",
            		        });
            				return false;
            			}else if((this.currentOrder.es_boleta_afecta() || this.currentOrder.es_factura_afecta()) && total_tax <= 0){
            		        this.showPopup('ErrorPopup',{
            		        	'title': "Error de integridad",
            		        	'body': "Debe haber almenos un producto afecto",
            		      	});
            				return false;
            		    };
            		};
            		if (this.currentOrder.is_to_invoice() || this.currentOrder.crear_guia() || this.currentOrder.es_boleta()) {
            			var ols = this.currentOrder.orderlines.models;
            			for(var i in ols){
            				if (ols[i].get_price_without_tax() < 0){
            						this.showPopup('ErrorPopup', {
            		        	'title': "Error de integridad",
            		        	'body': "No pueden ir valores negativos",
            		      	});
            						return false;
            				}
            			}
            		}
            		if ((this.currentOrder.is_to_invoice() || this.currentOrder.crear_guia()) && this.currentOrder.get_client()) {
            			var client = this.currentOrder.get_client();
            			if (!client.street){
            				this.showPopup('ErrorPopup',{
            					'title': 'Datos de Cliente Incompletos',
            					'body':  'El Cliente seleccionado no tiene la dirección, por favor verifique',
            				});
            				return false;
            			}
            			if (!client.document_number){
            				this.showPopup('ErrorPopup',{
            					'title': 'Datos de Cliente Incompletos',
            					'body':  'El Cliente seleccionado no tiene RUT, por favor verifique',
            				});
            				return false;
            			}
            			if (!client.activity_description){
            				this.showPopup('ErrorPopup',{
            					'title': 'Datos de Cliente Incompletos',
            					'body':  'El Cliente seleccionado no tiene Giro, por favor verifique',
            				});
            				return false;
            			}
            		}
            		if (res && Math.abs(this.currentOrder.get_total_with_tax() <= 0)) {
            			this.showPopup('ErrorPopup',{
            				'title': 'Orden con total 0',
            				'body':  'No puede emitir Pedidos con total 0, por favor asegurese que agrego lineas y que el precio es mayor a cero',
            			});
            			return false;
            		}
            		if (res && !this.currentOrder.is_to_invoice() && this.currentOrder.es_boleta()){
            			var start_number = 0;
            			var numero_ordenes = 0;
            			if (this.currentOrder.es_boleta_afecta()){
            				start_number = this.env.pos.pos_session.start_number;
            				numero_ordenes = this.env.pos.pos_session.numero_ordenes;
            			} else if (this.currentOrder.es_boleta_exenta()){
            				start_number = this.env.pos.pos_session.start_number_exentas;
            				numero_ordenes = this.env.pos.pos_session.numero_ordenes_exentas;
            			}
            			var caf_files = JSON.parse(this.currentOrder.sequence_id.caf_files);
            			var next_number = start_number + numero_ordenes;
            			next_number = this.env.pos.get_next_number(next_number, caf_files, start_number);
            			var caf_file = false;
            			for (var x in caf_files){
            				if(next_number >= caf_files[x].AUTORIZACION.CAF.DA.RNG.D && next_number <= caf_files[x].AUTORIZACION.CAF.DA.RNG.H){
            					caf_file =caf_files[x]
            				}
            			}
            			//validar que el numero emitido no supere el maximo del folio
            			if (!caf_file){
            				this.showPopup('ErrorPopup',{
            	        		'title': "Sin Folios disponibles",
            	                'body':  _.str.sprintf("No hay CAF para el folio de este documento: %(document_number)s " +
            	              		  "Solicite un nuevo CAF en el sitio www.sii.cl o utilice el asistente apicaf desde la secuencia", {
            	                			document_number: next_number,
            	              		  })
            	            });
            				return false;
        	        }
        		}
        		return res;
      	}

      	unset_boleta(){
      		this.currentOrder.unset_boleta();
      	}

      	click_boleta(){
      		this.currentOrder.set_to_invoice(false);
      		if (this.env.pos.pos_session.caf_files && !this.currentOrder.es_boleta_afecta()) {
      			this.currentOrder.set_boleta(true);
      			this.currentOrder.set_tipo(this.env.pos.config.secuencia_boleta);
      		}else{
                        this.unset_boleta();
                  }
      		this.render();
      	}

      	click_boleta_exenta(){
      		this.currentOrder.set_to_invoice(false);
      		if (this.env.pos.pos_session.caf_files_exentas && !this.currentOrder.es_boleta_exenta()){
      			this.currentOrder.set_boleta(true);
      			this.currentOrder.set_tipo(this.env.pos.config.secuencia_boleta_exenta);
      		}else{
                        this.unset_boleta();
                  }
      		this.render();
      	}

      	toggleIsToInvoice(){
      		this.unset_boleta();
          if(!this.env.pos.config.secuencia_factura_afecta){
            this.showPopup('ErrorPopup',{
                  'title': "No ha seleccionado secuencia de facturas",
                })
          }else{
        		this.currentOrder.set_to_invoice(!this.currentOrder.is_to_invoice());
        		if (this.currentOrder.is_to_invoice()){
        			this.currentOrder.set_tipo(this.env.pos.config.secuencia_factura_afecta);
        		}else{
        			this.currentOrder.unset_tipo();
        		}
          }
      		this.render();
      	}

      	click_factura_exenta(){
      		this.unset_boleta();
      		this.currentOrder.set_to_invoice(!this.currentOrder.is_to_invoice());
      		if (this.currentOrder.is_to_invoice()) {
      				this.currentOrder.set_tipo(this.env.pos.config.secuencia_factura_exenta);
      		} else {
      				this.currentOrder.unset_tipo();
      		}
      		this.render();
      	}

      }
      Registries.Component.extend(PaymentScreen, FEPaymentScreen);

      return FEPaymentScreen;
});
