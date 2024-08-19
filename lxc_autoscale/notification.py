import logging  # For logging notification events and errors
import requests  # For sending HTTP requests (used by Gotify and Uptime Kuma)
import smtplib  # For sending emails
from email.mime.text import MIMEText  # For constructing email messages
from abc import ABC, abstractmethod  # Abstract base classes for notification interfaces
from config import DEFAULTS  # Configuration values

# Abstract base class for notification proxies
class NotificationProxy(ABC):
    """
    Abstract class representing a generic notification proxy.
    Classes inheriting from this must implement the send_notification method.
    """
    @abstractmethod
    def send_notification(self, title: str, message: str, priority: int = 5):
        pass

# Gotify notification implementation
class GotifyNotification(NotificationProxy):
    """
    Notification class for sending notifications to a Gotify server.
    """
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token

    def send_notification(self, title: str, message: str, priority: int = 5):
        """
        Send a notification to a Gotify server.

        Args:
            title (str): The title of the notification.
            message (str): The body of the notification.
            priority (int): The priority level of the notification.
        """
        payload = {'title': title, 'message': message, 'priority': priority}
        headers = {'X-Gotify-Key': self.token}

        try:
            response = requests.post(f"{self.url}/message", data=payload, headers=headers)
            response.raise_for_status()
            logging.info(f"Gotify notification sent: {title} - {message}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Gotify notification failed: {e}")

# Email notification implementation
class EmailNotification(NotificationProxy):
    """
    Notification class for sending notifications via email.
    """
    def __init__(self, smtp_server: str, port: int, username: str, password: str, from_addr: str, to_addrs: list):
        self.smtp_server = smtp_server
        self.port = port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs

    def send_notification(self, title: str, message: str, priority: int = 5):
        """
        Send a notification via email.

        Args:
            title (str): The subject of the email.
            message (str): The body of the email.
            priority (int): Unused, but kept for interface consistency.
        """
        msg = MIMEText(message)
        msg['Subject'] = title
        msg['From'] = self.from_addr
        msg['To'] = ', '.join(self.to_addrs)

        try:
            with smtplib.SMTP(self.smtp_server, self.port) as server:
                server.starttls()  # Encrypt the connection
                server.login(self.username, self.password)  # Authenticate with the SMTP server
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())  # Send the email
            logging.info(f"Email sent: {title} - {message}")
        except Exception as e:
            logging.error(f"Failed to send email: {e}")

# Uptime Kuma notification implementation
class UptimeKumaNotification(NotificationProxy):
    """
    Notification class for sending notifications to Uptime Kuma via a webhook.
    """
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_notification(self, title: str, message: str, priority: int = 5):
        """
        Send a notification to Uptime Kuma using a webhook.

        Args:
            title (str): The title of the notification (unused by Uptime Kuma but kept for consistency).
            message (str): The body of the notification (unused by Uptime Kuma but kept for consistency).
            priority (int): Unused, but kept for interface consistency.
        """
        try:
            response = requests.get(self.webhook_url)
            if response.status_code == 200:
                logging.info("Uptime Kuma notification sent successfully")
            else:
                logging.error(f"Failed to send Uptime Kuma notification: {response.status_code}")
        except Exception as e:
            logging.error(f"Error sending Uptime Kuma notification: {e}")

# Send notification to all initialized notifiers
def send_notification(title, message, priority=5):
    """
    Send a notification through all configured notifiers.

    Args:
        title (str): The title of the notification.
        message (str): The body of the notification.
        priority (int): The priority of the notification (if applicable).
    """
    notifiers = initialize_notifiers()
    if notifiers:
        for notifier in notifiers:
            try:
                notifier.send_notification(title, message, priority)
            except Exception as e:
                logging.error(f"Failed to send notification using {notifier.__class__.__name__}: {e}")
    else:
        logging.warning("No notification system configured.")

# Initialize and return the list of configured notifiers
def initialize_notifiers():
    """
    Initialize all available notification mechanisms based on the configuration.

    Returns:
        list: A list of instantiated notifier objects.
    """
    notifiers = []

    # Initialize email notifier if SMTP settings are available
    if DEFAULTS.get('smtp_server') and DEFAULTS.get('smtp_username') and DEFAULTS.get('smtp_password'):
        try:
            email_notifier = EmailNotification(
                smtp_server=DEFAULTS['smtp_server'],
                port=DEFAULTS.get('smtp_port', 587),  # Default SMTP port is 587
                username=DEFAULTS['smtp_username'],
                password=DEFAULTS['smtp_password'],
                from_addr=DEFAULTS['smtp_from'],
                to_addrs=DEFAULTS['smtp_to']
            )
            notifiers.append(email_notifier)
        except Exception as e:
            logging.error(f"Failed to initialize Email notifier: {e}")

    # Initialize Gotify notifier if Gotify settings are available
    if DEFAULTS.get('gotify_url') and DEFAULTS.get('gotify_token'):
        try:
            gotify_notifier = GotifyNotification(DEFAULTS['gotify_url'], DEFAULTS['gotify_token'])
            notifiers.append(gotify_notifier)
        except Exception as e:
            logging.error(f"Failed to initialize Gotify notifier: {e}")

    # Initialize Uptime Kuma notifier if webhook URL is available
    if DEFAULTS.get('uptime_kuma_webhook_url'):
        try:
            uptime_kuma_notifier = UptimeKumaNotification(DEFAULTS['uptime_kuma_webhook_url'])
            notifiers.append(uptime_kuma_notifier)
        except Exception as e:
            logging.error(f"Failed to initialize Uptime Kuma notifier: {e}")

    return notifiers
