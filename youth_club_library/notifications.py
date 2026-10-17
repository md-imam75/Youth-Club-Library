import threading
from django.core.mail import send_mail
from django.conf import settings

def _send_admin_email_task(subject, message):
    try:
        from_email = settings.EMAIL_HOST_USER if hasattr(settings, 'EMAIL_HOST_USER') and settings.EMAIL_HOST_USER else settings.DEFAULT_FROM_EMAIL
        admin_email = getattr(settings, 'ADMIN_NOTIFICATION_EMAIL', 'imamsabbir20173@gmail.com')
        print(f"Sending email from {from_email} to {admin_email}")
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[admin_email],
            fail_silently=True,
        )
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send admin notification email: {e}")

def notify_admin_new_order(order):
    """Notify admin about a new online order (Buy or Borrow)."""
    subject = f"New {order.order_type} Order Received: {order.order_number}"
    
    user_info = f"{order.user.get_full_name()} ({order.user.email})" if order.user else "Walk-in/Guest"
    
    message = (
        f"A new {order.order_type.lower()} order has been placed.\n\n"
        f"Order Number: {order.order_number}\n"
        f"Customer: {user_info}\n"
        f"Book: {order.book.title}\n"
        f"Payment Method: {order.payment_method}\n"
        f"Total Amount: ৳{order.total_cost}\n\n"
        f"Log in to the admin panel to view full details."
    )
    
    threading.Thread(target=_send_admin_email_task, args=(subject, message)).start()

def notify_admin_new_membership(membership):
    """Notify admin about a new membership application."""
    subject = f"New Membership Application: {membership.unique_membership_id}"
    
    message = (
        f"A new membership application has been submitted.\n\n"
        f"User: {membership.user.get_full_name()} ({membership.user.email})\n"
        f"Plan: {membership.plan.name}\n"
        f"Payment Method: {membership.payment_method}\n"
        f"Transaction ID: {membership.transaction_id}\n\n"
        f"Log in to the admin panel to verify the payment and activate the membership."
    )
    
    threading.Thread(target=_send_admin_email_task, args=(subject, message)).start()

def notify_admin_new_book_request(book_req):
    """Notify admin about a new book request."""
    subject = f"New Book Request Submitted by {book_req.name}"
    
    items = book_req.items.all()
    items_list = "\n".join([f"- {item.book_title} by {item.author} (Qty: {item.quantity})" for item in items])
    
    message = (
        f"A new book request has been submitted.\n\n"
        f"Requester: {book_req.name}\n"
        f"Phone: {book_req.phone}\n"
        f"Email: {book_req.email}\n\n"
        f"Requested Books:\n{items_list}\n\n"
        f"Log in to the admin panel to view full details."
    )
    
    threading.Thread(target=_send_admin_email_task, args=(subject, message)).start()

def _send_user_status_task(email, subject, message):
    try:
        from_email = settings.EMAIL_HOST_USER if hasattr(settings, 'EMAIL_HOST_USER') and settings.EMAIL_HOST_USER else settings.DEFAULT_FROM_EMAIL
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[email],
            fail_silently=True,
        )
        print(f"Sent status update email to {email}")
    except Exception as e:
        print(f"Failed to send status email to {email}: {e}")

def notify_user_order_status(order, new_status):
    """Send an email to the order's user informing them of a status change."""
    if not order.user or not order.user.email:
        return
    subject = f"Your order {order.order_number} is now {new_status}"
    message = (
        f"Hello {order.user.get_full_name() or order.user.username},\n\n"
        f"Your order for '{order.book.title}' has been updated to status: {new_status}.\n"
        f"You can view the order details by logging into your account.\n\n"
        f"Thank you for using Youth Club Library."
    )
    threading.Thread(target=_send_user_status_task, args=(order.user.email, subject, message)).start()

