"""Notifier tool for sending emails and Slack messages."""

from typing import Any, Dict, List, Optional

import httpx

from config import get_settings
from tools.tool_manager import BaseTool


class NotifierTool(BaseTool):
    """Tool for sending notifications via email or Slack."""

    def __init__(self) -> None:
        """Initialize notifier tool."""
        super().__init__(
            name="notifier",
            description="Send notifications via email or Slack. Supports text and formatted messages.",
            parameters={
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "enum": ["email", "slack"],
                        "description": "Notification channel",
                    },
                    "recipient": {
                        "type": "string",
                        "description": "Email address or Slack channel",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Message subject (for email)",
                    },
                    "message": {
                        "type": "string",
                        "description": "Message content",
                    },
                },
                "required": ["channel", "recipient", "message"],
            },
            returns={
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "message_id": {"type": "string"},
                },
            },
            category="communication",
            tags=["notification", "email", "slack", "communication"],
            timeout=30,
        )
        self.settings = get_settings()

    def _execute(
        self,
        channel: str,
        recipient: str,
        message: str,
        subject: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send notification.

        Args:
            channel: Notification channel (email or slack)
            recipient: Recipient address or channel
            message: Message content
            subject: Message subject (for email)

        Returns:
            Dict containing success status and message ID
        """
        if channel == "email":
            return self._send_email(recipient, message, subject)
        elif channel == "slack":
            return self._send_slack(recipient, message)
        else:
            raise ValueError(f"Unknown notification channel: {channel}")

    def _send_email(
        self, recipient: str, message: str, subject: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send email notification using AWS SES.

        Args:
            recipient: Email address
            message: Message content
            subject: Email subject

        Returns:
            Dict with success status and message ID
        """
        # Placeholder for AWS SES integration
        # In production, use boto3 SES client:
        # import boto3
        # ses = boto3.client('ses', region_name=self.settings.aws_region)
        # response = ses.send_email(
        #     Source='noreply@example.com',
        #     Destination={'ToAddresses': [recipient]},
        #     Message={
        #         'Subject': {'Data': subject or 'Notification'},
        #         'Body': {'Text': {'Data': message}}
        #     }
        # )
        # return {"success": True, "message_id": response['MessageId']}

        self.logger.info(
            "Email notification (placeholder)",
            recipient=recipient,
            subject=subject,
        )

        return {
            "success": True,
            "message_id": "placeholder-email-id",
            "note": "Configure AWS SES for production email delivery",
        }

    def _send_slack(self, channel: str, message: str) -> Dict[str, Any]:
        """
        Send Slack notification using webhook.

        Args:
            channel: Slack channel
            message: Message content

        Returns:
            Dict with success status and message ID
        """
        webhook_url = self.settings.hitl_slack_webhook_url

        if not webhook_url:
            self.logger.warning("Slack webhook URL not configured")
            return {
                "success": False,
                "message_id": None,
                "note": "Configure HITL_SLACK_WEBHOOK_URL for Slack notifications",
            }

        try:
            payload = {
                "channel": channel,
                "text": message,
                "username": "Agentic AI Bot",
            }

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(webhook_url, json=payload)
                response.raise_for_status()

            self.logger.info("Slack notification sent", channel=channel)

            return {
                "success": True,
                "message_id": "slack-message-sent",
            }

        except Exception as e:
            self.logger.error("Failed to send Slack notification", error=str(e))
            return {
                "success": False,
                "message_id": None,
                "error": str(e),
            }

    async def _aexecute(
        self,
        channel: str,
        recipient: str,
        message: str,
        subject: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async version of execute."""
        if channel == "slack":
            webhook_url = self.settings.hitl_slack_webhook_url
            if not webhook_url:
                return {
                    "success": False,
                    "message_id": None,
                    "note": "Configure HITL_SLACK_WEBHOOK_URL",
                }

            try:
                payload = {
                    "channel": recipient,
                    "text": message,
                    "username": "Agentic AI Bot",
                }

                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(webhook_url, json=payload)
                    response.raise_for_status()

                return {"success": True, "message_id": "slack-message-sent"}

            except Exception as e:
                self.logger.error("Failed to send Slack notification", error=str(e))
                return {"success": False, "message_id": None, "error": str(e)}

        # Fall back to sync for email
        return self._execute(channel, recipient, message, subject)

