from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.utils import timezone

from .models import (
    Product,
    Order,
    CartItem,
    Notification,
    ActivityLog,
    DeliveryConfirmation,
)

from django.core.paginator import Paginator
from django.contrib import messages
from decimal import Decimal
import json
from django.http import JsonResponse
from django.contrib.auth import get_user_model
from accounts.models import Profile

User = get_user_model()


# ============================================================
# DASHBOARD
# ============================================================

@never_cache
@login_required
def dashboard(request):

    query = request.GET.get("q")

    products = Product.objects.select_related(
        "owner"
    ).all().order_by("-id")

    if query:
        products = products.filter(
            title__icontains=query
        )

    paginator = Paginator(
        products,
        12
    )

    page = request.GET.get("page")

    products = paginator.get_page(page)

    return render(
        request,
        "listings/index.html",
        {
            "products": products
        }
    )


# ============================================================
# ADD PRODUCT
# ============================================================

@login_required
def add_product(request):

    if request.method == "POST":

        image = request.FILES.get("image")

        print("FILES:", request.FILES)

        product = Product(
            owner=request.user,
            title=request.POST.get("title"),
            description=request.POST.get("description"),
            category=request.POST.get("category"),
            price=request.POST.get("price") or 0,
            stock=request.POST.get("stock") or 0,
        )

        if image:
            product.image = image

        product.save()

        ActivityLog.objects.create(
            user=request.user,
            action="Product Added",
            description=(
                f"Added product '{product.title}' "
                f"with stock {product.stock}."
            )
        )

        return redirect("listings:dashboard")

    return render(
        request,
        "listings/add_product.html"
    )


# ============================================================
# DELETE PRODUCT
# ============================================================

@login_required
def delete_product(request, pk):

    product = get_object_or_404(
        Product,
        pk=pk
    )

    if product.owner != request.user:
        return redirect(
            "listings:dashboard"
        )

    product_title = product.title

    product.delete()

    ActivityLog.objects.create(
        user=request.user,
        action="Product Deleted",
        description=(
            f"Deleted product '{product_title}'."
        )
    )

    return redirect(
        "listings:dashboard"
    )


# ============================================================
# ADD TO CART
# ============================================================

@login_required
def add_to_cart(request, pk):

    product = get_object_or_404(
        Product,
        pk=pk
    )

    if product.owner == request.user:

        messages.error(
            request,
            "You can't add your own product"
        )

        return redirect(
            "listings:dashboard"
        )

    if product.stock <= 0:

        messages.error(
            request,
            "This product is out of stock."
        )

        return redirect(
            "listings:dashboard"
        )

    item, created = CartItem.objects.get_or_create(
        user=request.user,
        product=product
    )

    if created:

        messages.success(
            request,
            "Added to cart"
        )

    else:

        if item.quantity >= product.stock:

            messages.warning(
                request,
                "You cannot add more than available stock."
            )

        else:

            messages.info(
                request,
                "Already in cart"
            )

    if request.GET.get("buy_now") == "1":

        return redirect(
            "listings:cart"
        )

    return redirect(
        "listings:dashboard"
    )


# ============================================================
# UPDATE CART
# ============================================================

@login_required
def update_cart(request, pk, action):

    item = get_object_or_404(
        CartItem,
        pk=pk,
        user=request.user
    )

    if action == "inc":

        if item.quantity >= item.product.stock:

            return JsonResponse({
                "success": False,
                "message": "Not enough stock available.",
                "deleted": False,
                "quantity": item.quantity,
                "item_id": pk
            })

        item.quantity += 1
        item.save()

    elif action == "dec":

        if item.quantity > 1:

            item.quantity -= 1
            item.save()

        else:

            item.delete()

    cart_items = CartItem.objects.filter(
        user=request.user
    )

    total = sum(
        i.product.price * i.quantity
        for i in cart_items
        if i.product.price
    )

    return JsonResponse({
        "success": True,
        "deleted": not item.pk,
        "quantity": item.quantity if item.pk else 0,
        "item_id": pk,
        "total": float(total)
    })


# ============================================================
# REMOVE FROM CART
# ============================================================

@login_required
def remove_from_cart(request, pk):

    cart_item = CartItem.objects.filter(
        id=pk,
        user=request.user
    ).first()

    if cart_item:
        cart_item.delete()

    return redirect(
        "listings:cart"
    )


# ============================================================
# CART
# ============================================================

@login_required
def cart_view(request):

    cart_items = CartItem.objects.filter(
        user=request.user
    ).select_related(
        "product"
    )

    total = Decimal("0.00")

    for item in cart_items:

        if item.product.price:

            total += (
                item.product.price *
                item.quantity
            )

    return render(
        request,
        "listings/cart.html",
        {
            "cart_items": cart_items,
            "total": total
        }
    )


# ============================================================
# BUY PRODUCT
# ============================================================

@login_required
def buy_product(request, pk):

    product = get_object_or_404(
        Product,
        pk=pk
    )

    if product.owner == request.user:
        return redirect(
            "listings:dashboard"
        )

    return render(
        request,
        "listings/checkout.html",
        {
            "product": product
        }
    )


# ============================================================
# CHECKOUT
# ============================================================

@login_required
def checkout(request):

    cart_items = CartItem.objects.filter(
        user=request.user
    ).select_related(
        "product"
    )

    if not cart_items.exists():

        return redirect(
            "listings:cart"
        )

    total = sum(
        i.product.price * i.quantity
        for i in cart_items
    )

    return render(
        request,
        "listings/checkout.html",
        {
            "cart_items": cart_items,
            "total": total
        }
    )


# ============================================================
# PLACE ORDER
# ============================================================

@login_required
def place_order_cart(request):

    if request.method != "POST":

        return JsonResponse({
            "success": False,
            "message": "POST required"
        })

    try:

        data = json.loads(
            request.body.decode("utf-8") or "{}"
        )

    except Exception:

        data = {}

    address = data.get(
        "address",
        ""
    )

    payment = data.get(
        "payment_method",
        "cod"
    )

    single_product_id = data.get(
        "product_id"
    )

    cart_items = CartItem.objects.filter(
        user=request.user
    ).select_related(
        "product"
    )

    last_order_id = None

    # ========================================================
    # SINGLE PRODUCT
    # ========================================================

    if single_product_id:

        product = get_object_or_404(
            Product,
            id=single_product_id
        )

        if product.owner == request.user:

            return JsonResponse({
                "success": False,
                "message": (
                    "You cannot order your own product."
                )
            })

        if product.stock < 1:

            return JsonResponse({
                "success": False,
                "message": "Product is out of stock."
            })

        order = Order.objects.create(
            buyer=request.user,
            product=product,
            quantity=1,
            address=address or "Not provided",
            payment_method=payment,
            status="pending"
        )

        # ====================================================
        # CREATE DELIVERY CONFIRMATION
        # ====================================================

        if product.owner:

            DeliveryConfirmation.objects.get_or_create(
                order=order,
                defaults={
                    "seller": product.owner
                }
            )

            Notification.objects.create(
                user=product.owner,
                order=order,
                message=(
                    f"New order received "
                    f"for {product.title}. "
                    f"Please confirm this delivery "
                    f"from your seller orders."
                )
            )

        ActivityLog.objects.create(
            user=request.user,
            action="Order Created",
            description=(
                f"Placed order #{order.id} "
                f"for {product.title}."
            )
        )

        last_order_id = order.id

    # ========================================================
    # CART
    # ========================================================

    else:

        if not cart_items.exists():

            return JsonResponse({
                "success": False,
                "message": "Cart empty"
            })

        # Check stock before creating orders
        for item in cart_items:

            if item.quantity > item.product.stock:

                return JsonResponse({
                    "success": False,
                    "message": (
                        f"Not enough stock for "
                        f"{item.product.title}. "
                        f"Available stock: "
                        f"{item.product.stock}"
                    )
                })

        for item in cart_items:

            order = Order.objects.create(
                buyer=request.user,
                product=item.product,
                quantity=item.quantity,
                address=address or "Not provided",
                payment_method=payment,
                status="pending"
            )

            owner = item.product.owner

            # =================================================
            # CREATE DELIVERY CONFIRMATION
            # =================================================

            if owner:

                DeliveryConfirmation.objects.get_or_create(
                    order=order,
                    defaults={
                        "seller": owner
                    }
                )

                Notification.objects.create(
                    user=owner,
                    order=order,
                    message=(
                        f"New order received "
                        f"for {item.product.title}. "
                        f"Please confirm this delivery "
                        f"from your seller orders."
                    )
                )

            ActivityLog.objects.create(
                user=request.user,
                action="Order Created",
                description=(
                    f"Placed order #{order.id} "
                    f"for {item.product.title}."
                )
            )

            last_order_id = order.id

        cart_items.delete()

    return JsonResponse({
        "success": True,
        "order_id": last_order_id
    })


# ============================================================
# PRODUCT DETAIL
# ============================================================

@login_required
def product_detail(request, pk):

    product = get_object_or_404(
        Product,
        pk=pk
    )

    return render(
        request,
        "listings/product_detail.html",
        {
            "product": product
        }
    )


# ============================================================
# ORDER DETAIL
# ============================================================

@login_required
def order_detail(request, pk):

    o = get_object_or_404(
        Order,
        id=pk,
        buyer=request.user
    )

    if request.headers.get(
        "X-Requested-With"
    ) == "XMLHttpRequest":

        return JsonResponse({
            "id": o.id,
            "product": o.product.title,
            "status": o.status,
            "quantity": o.quantity,
            "address": o.address,
            "price": o.product.price
        })

    return render(
        request,
        "listings/order_detail.html",
        {
            "order": o
        }
    )


# ============================================================
# ORDER HISTORY
# ============================================================

@login_required
def order_history(request):

    orders = Order.objects.filter(
        buyer=request.user
    )

    if request.headers.get(
        "X-Requested-With"
    ) == "XMLHttpRequest":

        data = list(
            orders.values(
                "id",
                "status",
                "product__title"
            )
        )

        return JsonResponse(
            data,
            safe=False
        )

    return render(
        request,
        "listings/orders.html",
        {
            "orders": orders
        }
    )


# ============================================================
# MY ORDERS
# ============================================================

@login_required
def my_orders(request):

    orders = Order.objects.filter(
        buyer=request.user
    ).exclude(
        status="cancelled"
    ).select_related(
        "product"
    ).order_by(
        "-created_at"
    )

    return render(
        request,
        "listings/my_orders.html",
        {
            "orders": orders
        }
    )


# ============================================================
# CANCEL ORDER
# ============================================================

@login_required
def cancel_order(request, pk):

    try:

        order = Order.objects.get(
            id=pk,
            buyer=request.user
        )

        if order.status == "cancelled":

            return JsonResponse({
                "success": False,
                "message": "Already cancelled"
            })

        if order.status == "delivered":

            return JsonResponse({
                "success": False,
                "message": (
                    "Delivered orders "
                    "cannot be cancelled"
                )
            })

        order.status = "cancelled"

        order.save()

        ActivityLog.objects.create(
            user=request.user,
            action="Order Cancelled",
            description=(
                f"Cancelled order #{order.id}."
            )
        )

        return JsonResponse({
            "success": True,
            "id": pk
        })

    except Order.DoesNotExist:

        return JsonResponse({
            "success": False,
            "message": "Order not found"
        })


# ============================================================
# NOTIFICATIONS
# ============================================================

@login_required
def notifications_view(request):

    notifications = Notification.objects.filter(
        user=request.user
    ).order_by(
        "-created_at"
    )

    return render(
        request,
        "listings/Notificationpage.html",
        {
            "notifications": notifications
        }
    )


# ============================================================
# OPEN NOTIFICATION
# ============================================================

@login_required
def open_notification(request, pk):

    notification = get_object_or_404(
        Notification,
        id=pk,
        user=request.user
    )

    if not notification.is_read:

        notification.is_read = True
        notification.save()

    return render(
        request,
        "listings/notification_detail.html",
        {
            "notification": notification,
            "order": notification.order
        }
    )


# ============================================================
# MARK NOTIFICATION READ
# ============================================================

@login_required
def mark_notification_read(request, pk):

    n = get_object_or_404(
        Notification,
        id=pk,
        user=request.user
    )

    n.is_read = True
    n.save()

    return redirect(
        "listings:notifications"
    )


# ============================================================
# USER PROFILE
# ============================================================

@login_required
def userProfileView(request, id):

    user_obj = get_object_or_404(
        User,
        id=id
    )

    profile = Profile.objects.filter(
        user=user_obj
    ).first()

    return render(
        request,
        "listings/userProfile.html",
        {
            "user_obj": user_obj,
            "profile": profile
        }
    )


# ============================================================
# USER MESSAGE
# ============================================================

@login_required
def userMessage(request, id):

    return render(
        request,
        "listings/messages.html",
        {
            "id": id
        }
    )


# ============================================================
# CONFIRM ORDER BY SELLER
# ============================================================

@login_required
def confirm_order(request, pk):

    order = get_object_or_404(
        Order,
        id=pk
    )

    if not order.product.owner:

        messages.error(
            request,
            "This product does not have a seller."
        )

        return redirect(
            "listings:notifications"
        )

    if order.product.owner != request.user:

        messages.error(
            request,
            "You are not authorized to confirm this order."
        )

        return redirect(
            "listings:notifications"
        )

    if order.status != "pending":

        messages.warning(
            request,
            "This order has already been processed."
        )

        return redirect(
            "listings:notifications"
        )

    order.status = "processing"

    order.save(
        update_fields=[
            "status"
        ]
    )

    # Make sure the delivery confirmation exists
    confirmation, created = (
        DeliveryConfirmation.objects.get_or_create(
            order=order,
            defaults={
                "seller": request.user
            }
        )
    )

    # Seller's order confirmation is not yet
    # the final delivery confirmation.
    # The seller must still confirm delivery.
    if not confirmation.seller:
        confirmation.seller = request.user
        confirmation.save(
            update_fields=[
                "seller"
            ]
        )

    if order.buyer:

        Notification.objects.create(
            user=order.buyer,
            order=order,
            message=(
                f"Your order for "
                f"'{order.product.title}' "
                f"has been confirmed. "
                f"Delivery in 3–5 days."
            )
        )

    ActivityLog.objects.create(
        user=request.user,
        action="Order Confirmed",
        description=(
            f"Confirmed order #{order.id}."
        )
    )

    messages.success(
        request,
        "Order confirmed"
    )

    return redirect(
        "listings:notifications"
    )


# ============================================================
# SELLER ORDERS
# ============================================================

@login_required
def seller_orders(request):

    orders = (
        Order.objects
        .filter(
            product__owner=request.user
        )
        .exclude(
            status="cancelled"
        )
        .exclude(
            status="delivered"
        )
        .select_related(
            "product",
            "buyer",
            "delivery_confirmation"
        )
        .order_by(
            "-created_at"
        )
    )

    return render(
        request,
        "listings/seller_orders.html",
        {
            "orders": orders
        }
    )


# ============================================================
# SELLER CONFIRM DELIVERY
# ============================================================

@login_required
def seller_confirm_delivery(request, order_id):

    if request.method != "POST":

        return redirect(
            "listings:seller_orders"
        )

    order = get_object_or_404(
        Order.objects.select_related(
            "product",
            "product__owner",
            "buyer"
        ),
        id=order_id
    )

    # ========================================================
    # PRODUCT SELLER
    # ========================================================

    if not order.product.owner:

        messages.error(
            request,
            "This product does not have a seller."
        )

        return redirect(
            "listings:seller_orders"
        )

    # ========================================================
    # ONLY PRODUCT OWNER
    # ========================================================

    if order.product.owner_id != request.user.id:

        messages.error(
            request,
            "You are not authorized to confirm this delivery."
        )

        return redirect(
            "listings:seller_orders"
        )

    # ========================================================
    # CANCELLED
    # ========================================================

    if order.status == "cancelled":

        messages.error(
            request,
            "Cancelled orders cannot be confirmed."
        )

        return redirect(
            "listings:seller_orders"
        )

    # ========================================================
    # ALREADY DELIVERED
    # ========================================================

    if order.status == "delivered":

        messages.warning(
            request,
            "This order has already been delivered."
        )

        return redirect(
            "listings:seller_orders"
        )

    # ========================================================
    # GET OR CREATE CONFIRMATION
    # ========================================================

    confirmation, created = (
        DeliveryConfirmation.objects.get_or_create(
            order=order,
            defaults={
                "seller": request.user
            }
        )
    )

    # ========================================================
    # ADMIN ALREADY COMPLETED
    # ========================================================

    if confirmation.admin_confirmed_at:

        messages.warning(
            request,
            "Admin has already completed this delivery."
        )

        return redirect(
            "listings:seller_orders"
        )

    # ========================================================
    # SELLER ALREADY CONFIRMED
    # ========================================================

    if confirmation.seller_confirmed_at:

        messages.warning(
            request,
            (
                "You have already confirmed this delivery. "
                "Waiting for admin confirmation."
            )
        )

        return redirect(
            "listings:seller_orders"
        )

    # ========================================================
    # SELLER CONFIRMATION
    # ========================================================

    confirmation.seller = request.user

    confirmation.seller_confirmed_at = timezone.now()

    confirmation.save(
        update_fields=[
            "seller",
            "seller_confirmed_at"
        ]
    )

    # ========================================================
    # SELLER ACTIVITY
    # ========================================================

    ActivityLog.objects.create(
        user=request.user,
        action="Delivery Confirmed",
        description=(
            f"Seller confirmed delivery for "
            f"Order #{order.id}. "
            f"Product: {order.product.title}."
        )
    )

    # ========================================================
    # NOTIFY ADMINS
    # ========================================================

    admins = User.objects.filter(
        is_admin=True
    )

    for admin in admins:

        Notification.objects.create(
            user=admin,
            order=order,
            message=(
                f"Seller confirmed delivery for "
                f"Order #{order.id}. "
                f"Admin confirmation is required."
            )
        )

    messages.success(
        request,
        (
            f"Delivery for Order #{order.id} "
            f"has been confirmed. "
            f"Waiting for admin confirmation."
        )
    )

    return redirect(
        "listings:seller_orders"
    )