from typing import Any


def _format_money_cents(value: Any, currency: str = "USD") -> str:
    try:
        amount = int(value) / 100
        return f"{amount:.2f} {currency.upper()}"
    except (TypeError, ValueError):
        return str(value or "")


def _payload_value(payload: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in payload and payload[key] not in (None, ""):
            return payload[key]

    return default


def render_email(
    *,
    template_code: str,
    template_data: dict[str, Any],
) -> tuple[str, str]:
    template_data = template_data or {}

    if template_code == "order_created":
        order_id = _payload_value(template_data, "order_id", default="ваш заказ")
        total = _payload_value(template_data, "total_amount_cents", "total_amount", default=None)
        currency = _payload_value(template_data, "currency", default="USD")

        subject = "Ваш заказ создан"
        body = (
            "Здравствуйте!\n\n"
            f"Ваш заказ {order_id} создан и ожидает оплаты.\n"
        )

        if total is not None:
            body += f"Сумма к оплате: {_format_money_cents(total, currency)}.\n"

        body += "\nПерейдите к оплате в личном кабинете Dropoff.\n\nDropoff"
        return subject, body

    if template_code == "payment_succeeded":
        order_id = _payload_value(template_data, "order_id", default="ваш заказ")

        subject = "Оплата прошла успешно"
        body = (
            "Здравствуйте!\n\n"
            f"Оплата по заказу {order_id} прошла успешно.\n"
            "Мы уведомим вас о дальнейших шагах по доставке или передаче вещи.\n\n"
            "Dropoff"
        )
        return subject, body

    if template_code == "payment_failed":
        order_id = _payload_value(template_data, "order_id", default="ваш заказ")

        subject = "Не удалось обработать оплату"
        body = (
            "Здравствуйте!\n\n"
            f"Не удалось обработать оплату по заказу {order_id}.\n"
            "Проверьте способ оплаты или попробуйте повторить оплату позже.\n\n"
            "Dropoff"
        )
        return subject, body

    if template_code == "delivery_created":
        order_id = _payload_value(template_data, "order_id", default="ваш заказ")

        subject = "Доставка создана"
        body = (
            "Здравствуйте!\n\n"
            f"По заказу {order_id} создана доставка.\n"
            "Следите за обновлениями в личном кабинете Dropoff.\n\n"
            "Dropoff"
        )
        return subject, body

    if template_code == "item_approved":
        title = _payload_value(template_data, "title", default="ваша вещь")

        subject = "Вещь опубликована"
        body = (
            "Здравствуйте!\n\n"
            f"Вещь «{title}» прошла модерацию и опубликована.\n\n"
            "Dropoff"
        )
        return subject, body

    if template_code == "item_rejected":
        title = _payload_value(template_data, "title", default="ваша вещь")
        comment = _payload_value(template_data, "moderation_comment", default=None)

        subject = "Вещь не прошла модерацию"
        body = (
            "Здравствуйте!\n\n"
            f"Вещь «{title}» не прошла модерацию.\n"
        )

        if comment:
            body += f"Комментарий модератора: {comment}\n"

        body += "\nDropoff"
        return subject, body

    subject = "Уведомление Dropoff"
    body = (
        "Здравствуйте!\n\n"
        "У вас новое уведомление в Dropoff.\n\n"
        f"Тип уведомления: {template_code}\n"
        f"Данные: {template_data}\n\n"
        "Dropoff"
    )
    return subject, body