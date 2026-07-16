"""Newsletter signup configuration.

The signup form posts the email address straight to your email provider
(Mailchimp, Kit/ConvertKit, Buttondown, MailerLite, etc.), so no email ever
touches this server and there are no API keys to manage.

To switch it on:
  1. Create a signup form in your email provider.
  2. Copy that form's POST action URL into FORM_ACTION below.
  3. Set EMAIL_FIELD to the field name your provider expects for the email
     address (Mailchimp uses "EMAIL", Kit uses "email_address",
     Buttondown uses "email"). Check your form's HTML if unsure.

Until FORM_ACTION is filled in, the footer shows a "coming soon" signup so
the design is in place but nothing posts anywhere.
"""

FORM_ACTION = ""      # e.g. "https://your.us1.list-manage.com/subscribe/post?u=..&id=.."
EMAIL_FIELD = "EMAIL"  # the email input's name attribute your provider expects


def enabled() -> bool:
    return bool(FORM_ACTION.strip())
