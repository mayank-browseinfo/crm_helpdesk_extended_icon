import openerp
from openerp.addons.crm import crm
from openerp.osv import fields, osv
from openerp import tools
from openerp.tools.translate import _
from openerp.tools import html2plaintext
from openerp import tools, SUPERUSER_ID,api
from openerp.tools.mail import plaintext2html
import base64
import logging
from email.utils import formataddr
from urlparse import urljoin
from openerp.addons.base.ir.ir_mail_server import MailDeliveryException
from openerp.tools.safe_eval import safe_eval as eval

_logger = logging.getLogger(__name__)


class crm_helpdesk(osv.osv):
    _inherit = 'crm.helpdesk'
    
    def _new_req_count(self, cr, uid, ids, arg, field_name, context=None):
        res = {}
        ids = ids[0]
        helpdesk_obj = self.pool['crm.helpdesk']
        hd_obj = helpdesk_obj.browse(cr, uid, ids)
        count = helpdesk_obj.search(cr, uid, [('state', '=', 'draft'), ('partner_id', '=', hd_obj.partner_id.id)], context=context)
        res[ids] = len(count)
        return res

    def _in_prog_req_count(self, cr, uid, ids, arg, field_name, context=None):
        res = {}
        ids = ids[0]
        helpdesk_obj = self.pool['crm.helpdesk']
        hd_obj = helpdesk_obj.browse(cr, uid, ids)
        count = helpdesk_obj.search(cr, uid, [('state', '=', 'open'), ('partner_id', '=', hd_obj.partner_id.id)], context=context)
        res[ids] = len(count)
        return res

    def _pend_req_count(self, cr, uid, ids, arg, field_name, context=None):
        res = {}
        ids = ids[0]
        helpdesk_obj = self.pool['crm.helpdesk']
        hd_obj = helpdesk_obj.browse(cr, uid, ids)
        count = helpdesk_obj.search(cr, uid, [('state', '=', 'pending'), ('partner_id', '=', hd_obj.partner_id.id)], context=context)
        res[ids] = len(count)
        return res

    def _close_req_count(self, cr, uid, ids, arg, field_name, context=None):
        res = {}
        ids = ids[0]
        helpdesk_obj = self.pool['crm.helpdesk']
        hd_obj = helpdesk_obj.browse(cr, uid, ids)
        count = helpdesk_obj.search(cr, uid, [('state', '=', 'done'), ('partner_id', '=', hd_obj.partner_id.id)], context=context)
        res[ids] = len(count)
        return res

    def _canc_req_count(self, cr, uid, ids, arg, field_name, context=None):
        res = {}
        ids = ids[0]
        helpdesk_obj = self.pool['crm.helpdesk']
        hd_obj = helpdesk_obj.browse(cr, uid, ids)
        count = helpdesk_obj.search(cr, uid, [('state', '=', 'cancel'), ('partner_id', '=', hd_obj.partner_id.id)], context=context)
        res[ids] = len(count)
        return res
        
    def _journal_item_count(self, cr, uid, ids, field_name, arg, context=None):
        res = dict(map(lambda x: (x,{'journal_item_count': 0, 'contracts_count': 0}), ids))
        MoveLine = self.pool('account.move.line')
        AnalyticAccount = self.pool('account.analytic.account')
        helpdesk_obj = self.pool['crm.helpdesk']
        hd_obj = helpdesk_obj.browse(cr, uid, ids)
        part_acc_move_line = len(MoveLine.search(cr, uid, [('partner_id', '=', hd_obj.partner_id.id)], context=context))
        part_anal_acc = len(AnalyticAccount.search(cr,uid, [('partner_id', '=', hd_obj.partner_id.id)], context=context))
        res[hd_obj.id]['journal_item_count'] = part_acc_move_line
        res[hd_obj.id]['contracts_count'] = part_anal_acc
        return res
        
             
    def _opportunity_meeting_phonecall_count(self, cr, uid, ids, field_name, arg, context=None):
        res = dict(map(lambda x: (x,{'opportunity_count': 0, 'meeting_count': 0}), ids))
        # the user may not have access rights for opportunities or meetings
        try:
            for hd_obj in self.browse(cr, uid, ids, context):
                opp_ids = self.pool['crm.lead'].search(cr, uid, [('partner_id', '=', hd_obj.partner_id.id), ('type', '=', 'opportunity'), ('probability', '<', '100')], context=context)
                meeting_id = self.pool['calendar.event'].search(cr, uid, [('partner_ids', '=', hd_obj.partner_id.id)])
                res[hd_obj.id] = {
                    'opportunity_count': len(opp_ids),
                    'meeting_count': len(meeting_id),
                }
        except:
            pass
        for hd_obj in self.browse(cr, uid, ids, context):
            phone_id = self.pool['crm.phonecall'].search(cr, uid, [('partner_id', '=', hd_obj.partner_id.id)])
            res[hd_obj.id]['phonecall_count'] = len(phone_id)
        return res
    
    def _invoice_total(self, cr, uid, ids, field_name, arg, context=None):
        result = {}
        account_invoice_report = self.pool.get('account.invoice.report')
        for helpdesk in self.browse(cr, uid, ids, context=context):
            domain = [('partner_id', 'child_of', helpdesk.partner_id.id)]
            invoice_ids = account_invoice_report.search(cr, uid, domain, context=context)
            invoices = account_invoice_report.browse(cr, uid, invoice_ids, context=context)
            result[helpdesk.id] = sum(inv.user_currency_price_total for inv in invoices)
        return result
    
    def _sale_order_count(self, cr, uid, ids, field_name, arg, context=None):
        res = dict(map(lambda x: (x,0), ids))
        # The current user may not have access rights for sale orders
        try:
            for helpdesk in self.browse(cr, uid, ids, context):
                res[helpdesk.id] = len(helpdesk.partner_id.sale_order_ids)
        except:
            pass
        return res
    
    def _claim_count(self, cr, uid, ids, field_name, arg, context=None):
        res = dict(map(lambda x: (x,0), ids))       
        Claim = self.pool['crm.claim']
        for helpdesk in self.browse(cr, uid, ids, context):
            claim_ids = Claim.search(cr, uid, [('partner_id', '=', helpdesk.partner_id.id)])
            res[helpdesk.id] = len(claim_ids)
        return res
    
    def _issue_count(self, cr, uid, ids, field_name, arg, context=None):
        res = dict(map(lambda x: (x,0), ids))               
        Issue = self.pool['project.issue']
        for helpdesk in self.browse(cr, uid, ids, context):
            issue_ids = Issue.search(cr, uid, [('partner_id', '=', helpdesk.partner_id.id)])
            res[helpdesk.id] = len(issue_ids)
        return res

    def _task_count(self, cr, uid, ids, field_name, arg, context=None):
        res = dict(map(lambda x: (x,0), ids))                       
        Task = self.pool['project.task']
        for helpdesk in self.browse(cr, uid, ids, context):
            task_ids = Task.search(cr, uid, [('partner_id', '=', helpdesk.partner_id.id)])
            res[helpdesk.id] = len(task_ids)
        return res

    
    _columns = {
        'new_req_count': fields.function(_new_req_count, string='New', type='integer'),
        'in_prog_req_count': fields.function(_in_prog_req_count, string='In Progress', type='integer'),
        'pend_req_count': fields.function(_pend_req_count, string='Pending', type='integer'),
        'close_req_count': fields.function(_close_req_count, string='Closed', type='integer'),
        'canc_req_count': fields.function(_canc_req_count, string='Cancelled', type='integer'),   
        'contracts_count': fields.function(_journal_item_count, string="Contracts", type='integer', multi="invoice_journal"),                
        'journal_item_count': fields.function(_journal_item_count, string="Journal Items", type="integer", multi="invoice_journal"),    
        'opportunity_count': fields.function(_opportunity_meeting_phonecall_count, string="Opportunity", type='integer', multi='opp_meet'),
        'meeting_count': fields.function(_opportunity_meeting_phonecall_count, string="Meetings", type='integer', multi='opp_meet'),
        'phonecall_count': fields.function(_opportunity_meeting_phonecall_count, string="Calls", type="integer", multi='opp_meet'), 
        'total_invoiced': fields.function(_invoice_total, string="Total Invoiced", type='float', groups='account.group_account_invoice'),
        'sale_order_count': fields.function(_sale_order_count, string='# of Sales Order', type='integer'),                               
        'claim_count': fields.function(_claim_count, string='# Claims', type='integer'),        
        'issue_count': fields.function(_issue_count, type='integer', string="Issues",),        
        'task_count': fields.function(_task_count, string='# Tasks', type='integer'),        
    }
    

class mail_notification(osv.Model):
    _inherit = 'mail.notification'
    
    def get_signature_footer(self, cr, uid, user_id, res_model=None, res_id=None, context=None, user_signature=True):
        """ Format a standard footer for notification emails (such as pushed messages
            notification or invite emails).
            Format:
                <p>--<br />
                    Administrator
                </p>
                <div>
                    <small>Sent from <a ...>Your Company</a> using <a ...>OpenERP</a>.</small>
                </div>
        """
        footer = ""

        if not user_id:
            return footer

        # add user signature
        user = self.pool.get("res.users").browse(cr, SUPERUSER_ID, [user_id], context=context)[0]
        if user_signature:
            if user.signature:
                signature = user.signature
            else:
                signature = "--<br />%s" % user.name
            footer = tools.append_content_to_html(footer, signature, plaintext=False)

        # add company signature
        if user.company_id.website:
            website_url = ('http://%s' % user.company_id.website) if not user.company_id.website.lower().startswith(('http:', 'https:')) \
                else user.company_id.website
            company = "<a style='color:inherit' href='%s'>%s</a>" % (website_url, user.company_id.name)
        else:
            company = user.company_id.name
        sent_by = _('Sent by %(company)s using %(odoo)s')
        if (context.get('default_res_model') and context.get('default_res_model') != 'crm.helpdesk') or (context.get('default_model') and context.get('default_model') != 'crm.helpdesk'):
            signature_company = '<br /><small>%s</small>' % (sent_by % {
                'company': company,
                'odoo': "<a style='color:inherit' href='https://www.odoo.com/'>Odoo</a>"
            })
            footer = tools.append_content_to_html(footer, signature_company, plaintext=False, container_tag='div')

        return footer
        
    
class mail_mail(osv.Model):
    _inherit = 'mail.mail'
    
    def _get_partner_access_link(self, cr, uid, mail, partner=None, context=None):
        """ Generate URLs for links in mails:
            - partner is not an user: signup_url
            - partner is an user: fallback on classic URL
        """
        res = ""
        if context is None:
            context = {}
        partner_obj = self.pool.get('res.partner')
        if partner and not partner.user_ids:
            contex_signup = dict(context, signup_valid=True)
            signup_url = partner_obj._get_signup_url_for_action(cr, SUPERUSER_ID, [partner.id],
                                                                action='mail.action_mail_redirect',
                                                                model=mail.model, res_id=mail.res_id,
                                                                context=contex_signup)[partner.id]
            if context.get('default_model') == 'crm.helpdesk':
                return res
            else:
                return ", <span class='oe_mail_footer_access'><small>%(access_msg)s <a style='color:inherit' href='%(portal_link)s'>%(portal_msg)s</a></small></span>" % {
                    'access_msg': _('access directly to'),
                    'portal_link': signup_url,
                    'portal_msg': '%s %s' % (context.get('model_name', ''), mail.record_name) if mail.record_name else _('your messages '),
                }
        else:
            return super(mail_mail, self)._get_partner_access_link(cr, uid, mail, partner=partner, context=context)
            
    def send(self, cr, uid, ids, auto_commit=False, raise_exception=False, context=None):
        """ Sends the selected emails immediately, ignoring their current
            state (mails that have already been sent should not be passed
            unless they should actually be re-sent).
            Emails successfully delivered are marked as 'sent', and those
            that fail to be deliver are marked as 'exception', and the
            corresponding error mail is output in the server logs.

            :param bool auto_commit: whether to force a commit of the mail status
                after sending each mail (meant only for scheduler processing);
                should never be True during normal transactions (default: False)
            :param bool raise_exception: whether to raise an exception if the
                email sending process has failed
            :return: True
        """
        context = dict(context or {})
        ir_mail_server = self.pool.get('ir.mail_server')
        ir_attachment = self.pool['ir.attachment']
        for mail in self.browse(cr, SUPERUSER_ID, ids, context=context):
            try:
                # TDE note: remove me when model_id field is present on mail.message - done here to avoid doing it multiple times in the sub method
                if mail.model:
                    model_id = self.pool['ir.model'].search(cr, SUPERUSER_ID, [('model', '=', mail.model)], context=context)[0]
                    model = self.pool['ir.model'].browse(cr, SUPERUSER_ID, model_id, context=context)
                else:
                    model = None
                if model:
                    context['model_name'] = model.name

                # load attachment binary data with a separate read(), as prefetching all
                # `datas` (binary field) could bloat the browse cache, triggerring
                # soft/hard mem limits with temporary data.
                attachment_ids = [a.id for a in mail.attachment_ids]
                attachments = [(a['datas_fname'], base64.b64decode(a['datas']))
                                 for a in ir_attachment.read(cr, SUPERUSER_ID, attachment_ids,
                                                             ['datas_fname', 'datas'])]

                # specific behavior to customize the send email for notified partners
                email_list = []
                if mail.email_to:
                    email_list.append(self.send_get_email_dict(cr, uid, mail, context=context))
                for partner in mail.recipient_ids:
                    email_list.append(self.send_get_email_dict(cr, uid, mail, partner=partner, context=context))
                # headers
                headers = {}
                bounce_alias = self.pool['ir.config_parameter'].get_param(cr, uid, "mail.bounce.alias", context=context)
                catchall_domain = self.pool['ir.config_parameter'].get_param(cr, uid, "mail.catchall.domain", context=context)
                if bounce_alias and catchall_domain:
                    if mail.model and mail.res_id:
                        headers['Return-Path'] = '%s-%d-%s-%d@%s' % (bounce_alias, mail.id, mail.model, mail.res_id, catchall_domain)
                    else:
                        headers['Return-Path'] = '%s-%d@%s' % (bounce_alias, mail.id, catchall_domain)
                if mail.headers:
                    try:
                        headers.update(eval(mail.headers))
                    except Exception:
                        pass

                # Writing on the mail object may fail (e.g. lock on user) which
                # would trigger a rollback *after* actually sending the email.
                # To avoid sending twice the same email, provoke the failure earlier
                mail.write({'state': 'exception'})
                mail_sent = False
                # build an RFC2822 email.message.Message object and send it without queuing
                res = None
                for email in email_list:
                    if mail.mail_message_id.model == 'crm.helpdesk':
                        # start custom code for send mail from 'Email Sent From' field
                        email_from1 = ''
                        reply_to1 = ''
                        crm_helpdesk_mails = self.pool.get('crm.helpdesk.emails').search(cr, uid, [])
                        if crm_helpdesk_mails:
                            crm_helpdesk_browse = self.pool.get('crm.helpdesk.emails').browse(cr, uid, crm_helpdesk_mails[0])
                            email_from1 = crm_helpdesk_browse.sent_from or ''
                            if crm_helpdesk_browse.reply_to:
                                reply_to1 = crm_helpdesk_browse.reply_to
                            else:
                                reply_to1 = crm_helpdesk_browse.sent_from
                    else:
                        email_from1 = mail.email_from
                        reply_to1 = mail.reply_to
                    # end custom code for send mail from 'Email Sent From' field
                    msg = ir_mail_server.build_email(
                        email_from=email_from1,
                        email_to=email.get('email_to'),
                        subject=email.get('subject'),
                        body=email.get('body'),
                        body_alternative=email.get('body_alternative'),
                        email_cc=tools.email_split(mail.email_cc),
                        reply_to=reply_to1,
                        attachments=attachments,
                        message_id=mail.message_id,
                        references=mail.references,
                        object_id=mail.res_id and ('%s-%s' % (mail.res_id, mail.model)),
                        subtype='html',
                        subtype_alternative='plain',
                        headers=headers)
                    try:
                        #check for ir mail server if is it configure or not if not then take default
                        server_id = ir_mail_server.search(cr, uid, [('smtp_user','=',email_from1)])
                        if server_id:
                            res = ir_mail_server.send_email(cr, uid, msg,
                                                        mail_server_id=server_id,
                                                        context=context)
                        else:
                            res = ir_mail_server.send_email(cr, uid, msg,
                                                    mail_server_id=mail.mail_server_id.id,
                                                    context=context)
                    except AssertionError as error:
                        if error.message == ir_mail_server.NO_VALID_RECIPIENT:
                            # No valid recipient found for this particular
                            # mail item -> ignore error to avoid blocking
                            # delivery to next recipients, if any. If this is
                            # the only recipient, the mail will show as failed.
                            _logger.warning("Ignoring invalid recipients for mail.mail %s: %s",
                                            mail.message_id, email.get('email_to'))
                        else:
                            raise
                if res:
                    mail.write({'state': 'sent', 'message_id': res})
                    mail_sent = True

                # /!\ can't use mail.state here, as mail.refresh() will cause an error
                # see revid:odo@openerp.com-20120622152536-42b2s28lvdv3odyr in 6.1
                if mail_sent:
                    _logger.info('Mail with ID %r and Message-Id %r successfully sent', mail.id, mail.message_id)
                self._postprocess_sent_message(cr, uid, mail, context=context, mail_sent=mail_sent)
            except MemoryError:
                # prevent catching transient MemoryErrors, bubble up to notify user or abort cron job
                # instead of marking the mail as failed
                _logger.exception('MemoryError while processing mail with ID %r and Msg-Id %r. '\
                                      'Consider raising the --limit-memory-hard startup option',
                                  mail.id, mail.message_id)
                raise
            except Exception as e:
                _logger.exception('failed sending mail.mail %s', mail.id)
                mail.write({'state': 'exception'})
                self._postprocess_sent_message(cr, uid, mail, context=context, mail_sent=False)
                if raise_exception:
                    if isinstance(e, AssertionError):
                        # get the args of the original error, wrap into a value and throw a MailDeliveryException
                        # that is an except_orm, with name and value as arguments
                        value = '. '.join(e.args)
                        raise MailDeliveryException(_("Mail Delivery Failed"), value)
                    raise

            if auto_commit is True:
                cr.commit()
        return True
    
    
class crm_helpdesk_emails(osv.osv):
    _name = 'crm.helpdesk.emails'
    _columns = {
            'sent_from': fields.char('Email Sent From'),
            'reply_to': fields.char('Reply To'),
            'model_id':fields.many2one('ir.model','Model')
    }


