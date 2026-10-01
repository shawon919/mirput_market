import random
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.shortcuts import (
    render,
    redirect,
    get_object_or_404
)

from django.contrib.auth import (
    authenticate,
    login,
    logout,
    get_user_model
)

from django.contrib import messages

from django.contrib.auth.decorators import login_required

from django.utils import timezone

from django.core.cache import cache

from django.core.mail import send_mail

from django.db import transaction

from django.db.models import (
    Sum,
    Count,
    Q
)

from django.db.models.functions import TruncDate, TruncMonth

from .models import OTP, Profile

from listings.models import (
    Product,
    Order,
    Sale,
    ActivityLog,
    Notification,
    AppRevenue,
    DeliveryConfirmation
)


User = get_user_model()


# ============================================================
# ADMIN PERMISSION HELPER
# ============================================================

def is_admin_user(user):

    return (
        user.is_authenticated
        and
        (
            user.is_admin
            or
            user.is_superuser
        )
    )


# ============================================================
# OTP
# ============================================================

def generate_otp(email, purpose="verify"):

    OTP.objects.filter(
        email=email,
        purpose=purpose
    ).delete()

    code = str(
        random.randint(
            100000,
            999999
        )
    )

    otp = OTP.objects.create(
        email=email,
        code=code,
        purpose=purpose
    )

    send_mail(
        subject="Your OTP Code",
        message=f"Your OTP code is {code}",
        from_email="noreply@market.com",
        recipient_list=[email]
    )

    print(
        "NEW OTP:",
        code,
        flush=True
    )

    return otp


def resend_otp(request, user_id):

    user = User.objects.get(
        id=user_id
    )

    last_otp = OTP.objects.filter(
        email=user.email
    ).order_by(
        "-created_at"
    ).first()

    if (
        last_otp
        and
        (timezone.now() - last_otp.created_at).seconds < 60
    ):

        messages.error(
            request,
            "Wait 60 seconds before resending OTP"
        )

        return redirect(
            request.META.get(
                "HTTP_REFERER"
            )
        )

    OTP.objects.filter(
        email=user.email,
        is_used=False
    ).update(
        is_used=True
    )

    generate_otp(
        user.email,
        "verify"
    )

    messages.success(
        request,
        "OTP resent successfully"
    )

    return redirect(
        f"/accounts/verify/{user.id}/"
    )


# ============================================================
# REGISTER
# ============================================================

def register(request):

    if request.method == "POST":

        username = request.POST.get(
            "username"
        )

        email = request.POST.get(
            "email"
        )

        password = request.POST.get(
            "password"
        )

        if User.objects.filter(
            email=email
        ).exists():

            messages.error(
                request,
                "Email already exists"
            )

            return redirect(
                "register"
            )

        if User.objects.filter(
            username=username
        ).exists():

            messages.error(
                request,
                "Username already exists"
            )

            return redirect(
                "register"
            )

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        user.is_active = False

        user.is_email_verified = False

        user.save()

        generate_otp(
            user.email,
            "verify"
        )

        return redirect(
            f"/accounts/verify/{user.id}/"
        )

    return render(
        request,
        "accounts/register.html"
    )


# ============================================================
# VERIFY OTP
# ============================================================

def verify_otp(request, user_id):

    user = get_object_or_404(
        User,
        id=user_id
    )

    if request.method == "POST":

        code = request.POST.get(
            "otp",
            ""
        ).strip()

        otp = OTP.objects.filter(
            email=user.email,
            code=code,
            purpose="verify",
            is_used=False
        ).order_by(
            "-created_at"
        ).first()

        if otp and otp.is_valid():

            user.is_active = True

            user.is_email_verified = True

            user.save()

            otp.is_used = True

            otp.save()

            login(
                request,
                user,
                backend="django.contrib.auth.backends.ModelBackend"
            )

            ActivityLog.objects.create(
                user=user,
                action="Account Verified",
                description="User verified their email account."
            )

            OTP.objects.filter(
                email=user.email,
                purpose="verify"
            ).delete()

            return redirect(
                "/accounts/dashboard/"
            )

        else:

            messages.error(
                request,
                "Invalid OTP. Please try again."
            )

    return render(
        request,
        "accounts/verify.html",
        {
            "user": user
        }
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@login_required
def adminpanel(request):

    if not is_admin_user(request.user):

        return redirect(
            "/accounts/dashboard/"
        )

    today = timezone.localdate()

    start_of_month = today.replace(
        day=1
    )

    # ========================================================
    # BASIC STATISTICS
    # ========================================================

    total_users = User.objects.count()

    total_products = Product.objects.count()

    total_stock = (
        Product.objects.aggregate(
            total=Sum("stock")
        )["total"] or 0
    )

    total_orders = (
        Order.objects
        .exclude(
            status="cancelled"
        )
        .count()
    )

    completed_deliveries = (
        Order.objects
        .filter(
            status="delivered"
        )
        .count()
    )

    pending_orders = (
        Order.objects
        .filter(
            status="pending"
        )
        .count()
    )

    # ========================================================
    # SALES
    # ========================================================

    total_sales = (
        Sale.objects.aggregate(
            total=Sum("total_amount")
        )["total"] or Decimal("0.00")
    )

    daily_sales = (
        Sale.objects
        .filter(
            sold_at__date=today
        )
        .aggregate(
            total=Sum("total_amount")
        )["total"] or Decimal("0.00")
    )

    monthly_sales = (
        Sale.objects
        .filter(
            sold_at__date__gte=start_of_month
        )
        .aggregate(
            total=Sum("total_amount")
        )["total"] or Decimal("0.00")
    )

    # ========================================================
    # APP REVENUE
    # WEBSITE GETS 30% OF COMPLETED SALES
    # ========================================================

    total_app_revenue = (
        AppRevenue.objects
        .aggregate(
            total=Sum("revenue_amount")
        )["total"] or Decimal("0.00")
    )

    today_app_revenue = (
        AppRevenue.objects
        .filter(
            created_at__date=today
        )
        .aggregate(
            total=Sum("revenue_amount")
        )["total"] or Decimal("0.00")
    )

    monthly_app_revenue = (
        AppRevenue.objects
        .filter(
            created_at__date__gte=start_of_month
        )
        .aggregate(
            total=Sum("revenue_amount")
        )["total"] or Decimal("0.00")
    )

    # ========================================================
    # PENDING DELIVERY CONFIRMATIONS
    # ========================================================

    pending_delivery_count = (
        DeliveryConfirmation.objects
        .filter(
            seller_confirmed_at__isnull=False,
            admin_confirmed_at__isnull=True
        )
        .count()
    )

    # ========================================================
    # USER OVERVIEW
    # ========================================================

    user_overview = []

    for user in User.objects.all().order_by(
        "-date_joined"
    ):

        products = Product.objects.filter(
            owner=user
        )

        sales = Sale.objects.filter(
            seller=user
        )

        current_stock = (
            products.aggregate(
                total=Sum("stock")
            )["total"] or 0
        )

        user_total_sales = (
            sales.aggregate(
                total=Sum("total_amount")
            )["total"] or Decimal("0.00")
        )

        user_daily_sales = (
            sales
            .filter(
                sold_at__date=today
            )
            .aggregate(
                total=Sum("total_amount")
            )["total"] or Decimal("0.00")
        )

        user_monthly_sales = (
            sales
            .filter(
                sold_at__date__gte=start_of_month
            )
            .aggregate(
                total=Sum("total_amount")
            )["total"] or Decimal("0.00")
        )

        account_age = (
            today -
            user.date_joined.date()
        ).days

        user_overview.append({

            "user":
                user,

            "account_age":
                account_age,

            "total_products":
                products.count(),

            "current_stock":
                current_stock,

            "total_sales":
                user_total_sales,

            "daily_sales":
                user_daily_sales,

            "monthly_sales":
                user_monthly_sales,

            "activity_status":
                (
                    "Active"
                    if user.is_active
                    else "Inactive"
                ),

        })

    # ========================================================
    # RECENT ORDERS
    # ========================================================

    recent_orders = (
        Order.objects
        .select_related(
            "buyer",
            "product",
            "product__owner"
        )
        .exclude(
            status="cancelled"
        )
        .order_by(
            "-created_at"
        )[:50]
    )

    # ========================================================
    # RECENT SALES
    # ========================================================

    recent_sales = (
        Sale.objects
        .select_related(
            "seller",
            "buyer",
            "product",
            "order"
        )
        .order_by(
            "-sold_at"
        )[:50]
    )

    # ========================================================
    # ADMIN PANEL
    # ========================================================

    return render(
        request,
        "accounts/admin_panel.html",
        {

            # BASIC STATISTICS

            "total_users":
                total_users,

            "total_products":
                total_products,

            "total_stock":
                total_stock,

            "total_orders":
                total_orders,

            "completed_deliveries":
                completed_deliveries,

            "pending_orders":
                pending_orders,


            # SALES

            "total_sales":
                total_sales,

            "daily_sales":
                daily_sales,

            "monthly_sales":
                monthly_sales,


            # WEBSITE REVENUE

            "total_app_revenue":
                total_app_revenue,

            "today_app_revenue":
                today_app_revenue,

            "monthly_app_revenue":
                monthly_app_revenue,


            # DELIVERY

            "pending_delivery_count":
                pending_delivery_count,


            # USER OVERVIEW

            "user_overview":
                user_overview,


            # RECENT ORDERS

            "recent_orders":
                recent_orders,


            # RECENT SALES

            "recent_sales":
                recent_sales,

        }
    )


# ============================================================
# ADMIN DELIVERY CONFIRMATIONS
# ============================================================

@login_required
def admin_delivery_confirmations(request):

    if not is_admin_user(request.user):

        return redirect(
            "/accounts/dashboard/"
        )

    # --------------------------------------------------------
    # SELLER CONFIRMED
    # BUT ADMIN HAS NOT CONFIRMED
    # --------------------------------------------------------

    pending_confirmations = (
        DeliveryConfirmation.objects
        .filter(
            seller_confirmed_at__isnull=False,
            admin_confirmed_at__isnull=True
        )
        .select_related(
            "order",
            "order__buyer",
            "order__product",
            "seller"
        )
        .order_by(
            "-seller_confirmed_at"
        )
    )

    # --------------------------------------------------------
    # RECENT ADMIN CONFIRMED
    # --------------------------------------------------------

    completed_confirmations = (
        DeliveryConfirmation.objects
        .filter(
            admin_confirmed_at__isnull=False
        )
        .select_related(
            "order",
            "order__buyer",
            "order__product",
            "seller",
            "admin_confirmed_by"
        )
        .order_by(
            "-admin_confirmed_at"
        )[:50]
    )

    return render(
        request,
        "accounts/admin_delivery_confirmations.html",
        {
            "pending_confirmations":
                pending_confirmations,

            "completed_confirmations":
                completed_confirmations,
        }
    )


# ============================================================
# COMPLETE DELIVERY
# ============================================================

@login_required
@transaction.atomic
def complete_delivery(request, order_id):

    if not is_admin_user(request.user):

        return redirect(
            "/accounts/dashboard/"
        )

    if request.method != "POST":

        return redirect(
            "admin_delivery_confirmations"
        )

    # ========================================================
    # GET ORDER WITH LOCK
    # ========================================================

    order = (
        Order.objects
        .select_for_update()
        .select_related(
            "product",
            "product__owner",
            "buyer"
        )
        .filter(
            id=order_id
        )
        .first()
    )

    if not order:

        messages.error(
            request,
            "Order not found."
        )

        return redirect(
            "admin_delivery_confirmations"
        )

    # ========================================================
    # PREVENT DUPLICATE DELIVERY
    # ========================================================

    if order.stock_deducted:

        messages.warning(
            request,
            "This order has already been completed."
        )

        return redirect(
            "admin_delivery_confirmations"
        )

    if order.status == "delivered":

        messages.warning(
            request,
            "This order is already delivered."
        )

        return redirect(
            "admin_delivery_confirmations"
        )

    if order.status == "cancelled":

        messages.error(
            request,
            "Cancelled orders cannot be delivered."
        )

        return redirect(
            "admin_delivery_confirmations"
        )

    # ========================================================
    # CHECK SELLER DELIVERY CONFIRMATION
    # ========================================================

    confirmation = (
        DeliveryConfirmation.objects
        .select_for_update()
        .filter(
            order=order
        )
        .first()
    )

    if not confirmation:

        messages.error(
            request,
            "Seller has not confirmed this delivery yet."
        )

        return redirect(
            "admin_delivery_confirmations"
        )

    if not confirmation.seller_confirmed_at:

        messages.error(
            request,
            "Seller must confirm the delivery first."
        )

        return redirect(
            "admin_delivery_confirmations"
        )

    if confirmation.admin_confirmed_at:

        messages.warning(
            request,
            "This delivery has already been confirmed by admin."
        )

        return redirect(
            "admin_delivery_confirmations"
        )

    # ========================================================
    # GET PRODUCT WITH LOCK
    # ========================================================

    product = (
        Product.objects
        .select_for_update()
        .get(
            id=order.product.id
        )
    )

    # ========================================================
    # CHECK STOCK
    # ========================================================

    if product.stock < order.quantity:

        messages.error(
            request,
            (
                f"Not enough stock for "
                f"{product.title}. "
                f"Available: {product.stock}, "
                f"Required: {order.quantity}."
            )
        )

        return redirect(
            "admin_delivery_confirmations"
        )

    # ========================================================
    # CALCULATE SALE
    # ========================================================

    unit_price = product.price

    quantity = order.quantity

    total_amount = (
        unit_price * quantity
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    cost_price = product.cost_price or Decimal("0.00")

    cost_amount = (
        cost_price * quantity
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    # ========================================================
    # CALCULATE PRODUCT PROFIT
    # ========================================================

    profit_amount = (
        total_amount -
        cost_amount
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    # ========================================================
    # APP REVENUE
    #
    # App receives 30% of the COMPLETED SALE AMOUNT.
    # ========================================================

    revenue_percentage = Decimal("30.00")

    revenue_amount = (
        total_amount *
        revenue_percentage /
        Decimal("100")
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    # ========================================================
    # UPDATE PRODUCT STOCK
    # ========================================================

    product.stock -= quantity

    product.sold_quantity += quantity

    product.save(
        update_fields=[
            "stock",
            "sold_quantity",
            "updated_at"
        ]
    )

    # ========================================================
    # UPDATE ORDER
    # ========================================================

    order.status = "delivered"

    order.delivered_at = timezone.now()

    order.stock_deducted = True

    order.save(
        update_fields=[
            "status",
            "delivered_at",
            "stock_deducted"
        ]
    )

    # ========================================================
    # CREATE SALE
    # ========================================================

    sale = None

    if product.owner:

        sale = Sale.objects.create(
            order=order,
            seller=product.owner,
            buyer=order.buyer,
            product=product,
            quantity=quantity,
            unit_price=unit_price,
            total_amount=total_amount,
            sold_at=timezone.now()
        )

        # ----------------------------------------------------
        # SELLER ACTIVITY
        # ----------------------------------------------------

        ActivityLog.objects.create(
            user=product.owner,
            action="Sale Completed",
            description=(
                f"Order #{order.id} completed. "
                f"Product: {product.title}. "
                f"Quantity sold: {quantity}. "
                f"Total sale: {total_amount}."
            )
        )

    # ========================================================
    # CREATE APP REVENUE
    # ========================================================

    AppRevenue.objects.create(
        order=order,
        sale=sale,
        gross_amount=total_amount,
        cost_amount=cost_amount,
        profit_amount=profit_amount,
        revenue_percentage=revenue_percentage,
        revenue_amount=revenue_amount,
        created_at=timezone.now()
    )

    # ========================================================
    # UPDATE DELIVERY CONFIRMATION
    # ========================================================

    confirmation.admin_confirmed_at = timezone.now()

    confirmation.admin_confirmed_by = request.user

    confirmation.save(
        update_fields=[
            "admin_confirmed_at",
            "admin_confirmed_by"
        ]
    )

    # ========================================================
    # BUYER ACTIVITY
    # ========================================================

    ActivityLog.objects.create(
        user=order.buyer,
        action="Order Delivered",
        description=(
            f"Order #{order.id} "
            f"for '{product.title}' "
            f"has been delivered."
        )
    )

    # ========================================================
    # BUYER NOTIFICATION
    # ========================================================

    Notification.objects.create(
        user=order.buyer,
        order=order,
        message=(
            f"Your order #{order.id} "
            f"for '{product.title}' "
            f"has been delivered."
        )
    )

    # ========================================================
    # SELLER NOTIFICATION
    # ========================================================

    if product.owner:

        Notification.objects.create(
            user=product.owner,
            order=order,
            message=(
                f"Order #{order.id} "
                f"for '{product.title}' "
                f"has been completed. "
                f"Sold quantity: {quantity}. "
                f"Sale amount: {total_amount}."
            )
        )

    # ========================================================
    # ADMIN ACTIVITY
    # ========================================================

    ActivityLog.objects.create(
        user=request.user,
        action="Delivery Completed",
        description=(
            f"Admin completed Order #{order.id}. "
            f"Sale: {total_amount}. "
            f"Cost: {cost_amount}. "
            f"Profit: {profit_amount}. "
            f"App revenue: {revenue_amount}."
        )
    )

    messages.success(
        request,
        (
            f"Order #{order.id} completed successfully. "
            f"App revenue: {revenue_amount}."
        )
    )

    return redirect(
        "admin_delivery_confirmations"
    )


# ============================================================
# ADMIN REVENUE
# ============================================================

@login_required
def admin_revenue(request):

    if not is_admin_user(request.user):

        return redirect(
            "/accounts/dashboard/"
        )

    today = timezone.localdate()

    start_of_month = today.replace(
        day=1
    )

    # ========================================================
    # REVENUE TOTALS
    # ========================================================

    total_app_revenue = (
        AppRevenue.objects.aggregate(
            total=Sum("revenue_amount")
        )["total"] or 0
    )

    today_app_revenue = (
        AppRevenue.objects.filter(
            created_at__date=today
        ).aggregate(
            total=Sum("revenue_amount")
        )["total"] or 0
    )

    monthly_app_revenue = (
        AppRevenue.objects.filter(
            created_at__date__gte=start_of_month
        ).aggregate(
            total=Sum("revenue_amount")
        )["total"] or 0
    )

    # ========================================================
    # TOTAL GROSS
    # ========================================================

    total_gross_amount = (
        AppRevenue.objects.aggregate(
            total=Sum("gross_amount")
        )["total"] or 0
    )

    # ========================================================
    # TOTAL COST
    # ========================================================

    total_cost_amount = (
        AppRevenue.objects.aggregate(
            total=Sum("cost_amount")
        )["total"] or 0
    )

    # ========================================================
    # TOTAL PROFIT
    # ========================================================

    total_profit_amount = (
        AppRevenue.objects.aggregate(
            total=Sum("profit_amount")
        )["total"] or 0
    )

    # ========================================================
    # DAILY REVENUE
    # ========================================================

    daily_revenue = (
        AppRevenue.objects
        .annotate(
            day=TruncDate("created_at")
        )
        .values(
            "day"
        )
        .annotate(
            total=Sum("revenue_amount")
        )
        .order_by(
            "-day"
        )
    )

    # ========================================================
    # MONTHLY REVENUE
    # ========================================================

    monthly_revenue = (
        AppRevenue.objects
        .annotate(
            month=TruncMonth("created_at")
        )
        .values(
            "month"
        )
        .annotate(
            total=Sum("revenue_amount")
        )
        .order_by(
            "-month"
        )
    )

    # ========================================================
    # REVENUE TRANSACTIONS
    # ========================================================

    transactions = (
        AppRevenue.objects
        .select_related(
            "order",
            "order__buyer",
            "order__product",
            "sale",
            "sale__seller"
        )
        .order_by(
            "-created_at"
        )[:100]
    )

    return render(
        request,
        "accounts/admin_revenue.html",
        {
            "total_app_revenue":
                total_app_revenue,

            "today_app_revenue":
                today_app_revenue,

            "monthly_app_revenue":
                monthly_app_revenue,

            "total_gross_amount":
                total_gross_amount,

            "total_cost_amount":
                total_cost_amount,

            "total_profit_amount":
                total_profit_amount,

            "daily_revenue":
                daily_revenue,

            "monthly_revenue":
                monthly_revenue,

            "transactions":
                transactions,
        }
    )


# ============================================================
# ADMIN USER DETAILS
# ============================================================

@login_required
def admin_user_detail(request, user_id):

    if not is_admin_user(request.user):

        return redirect(
            "/accounts/dashboard/"
        )

    user_obj = get_object_or_404(
        User,
        id=user_id
    )

    profile, _ = Profile.objects.get_or_create(
        user=user_obj
    )

    products = Product.objects.filter(
        owner=user_obj
    ).order_by(
        "-created_at"
    )

    sales = Sale.objects.filter(
        seller=user_obj
    ).select_related(
        "buyer",
        "product",
        "order"
    ).order_by(
        "-sold_at"
    )

    orders = Order.objects.filter(
        product__owner=user_obj
    ).exclude(
        status="cancelled"
    ).select_related(
        "buyer",
        "product"
    ).order_by(
        "-created_at"
    )

    activities = ActivityLog.objects.filter(
        user=user_obj
    ).order_by(
        "-created_at"
    )

    today = timezone.localdate()

    start_of_month = today.replace(
        day=1
    )

    total_stock = (
        products.aggregate(
            total=Sum("stock")
        )["total"] or 0
    )

    total_sales = (
        sales.aggregate(
            total=Sum("total_amount")
        )["total"] or 0
    )

    daily_sales = (
        sales.filter(
            sold_at__date=today
        ).aggregate(
            total=Sum("total_amount")
        )["total"] or 0
    )

    monthly_sales = (
        sales.filter(
            sold_at__date__gte=start_of_month
        ).aggregate(
            total=Sum("total_amount")
        )["total"] or 0
    )

    total_sold_quantity = (
        sales.aggregate(
            total=Sum("quantity")
        )["total"] or 0
    )

    account_age = (
        today -
        user_obj.date_joined.date()
    ).days

    return render(
        request,
        "accounts/admin_user_detail.html",
        {
            "user_obj": user_obj,
            "profile": profile,
            "products": products,
            "sales": sales,
            "orders": orders,
            "activities": activities,
            "total_stock": total_stock,
            "total_sales": total_sales,
            "daily_sales": daily_sales,
            "monthly_sales": monthly_sales,
            "total_sold_quantity":
                total_sold_quantity,
            "account_age": account_age,
        }
    )


# ============================================================
# ADMIN USERS
# ============================================================

@login_required
def admin_users(request):

    if not is_admin_user(request.user):

        return redirect(
            "/accounts/dashboard/"
        )

    users = User.objects.all().order_by(
        "-date_joined"
    )

    return render(
        request,
        "accounts/admin_users.html",
        {
            "users": users
        }
    )


# ============================================================
# ADMIN SALES PAGE
# ============================================================

@login_required
def admin_sales(request):

    if not is_admin_user(request.user):

        return redirect(
            "/accounts/dashboard/"
        )

    sales = Sale.objects.select_related(
        "seller",
        "buyer",
        "product",
        "order"
    ).order_by(
        "-sold_at"
    )

    total_sales = (
        sales.aggregate(
            total=Sum("total_amount")
        )["total"] or 0
    )

    total_quantity = (
        sales.aggregate(
            total=Sum("quantity")
        )["total"] or 0
    )

    return render(
        request,
        "accounts/admin_sales.html",
        {
            "sales": sales,
            "total_sales": total_sales,
            "total_quantity": total_quantity,
        }
    )


# ============================================================
# LOGIN
# ============================================================

def login_view(request):

    if request.method == "POST":

        email = request.POST.get(
            "email"
        )

        password = request.POST.get(
            "password"
        )

        user = authenticate(
            request,
            username=email,
            password=password
        )

        print(
            "EMAIL:",
            email
        )

        print(
            "USER:",
            user
        )

        if user is None:

            messages.error(
                request,
                "Invalid email or password"
            )

            return redirect(
                "login"
            )

        if not user.is_active:

            messages.error(
                request,
                "Account not verified"
            )

            return redirect(
                "login"
            )

        login(
            request,
            user
        )

        print(
            "IS ADMIN:",
            user.is_admin
        )

        print(
            "IS SUPERUSER:",
            user.is_superuser
        )

        if user.is_admin or user.is_superuser:

            return redirect(
                "adminpanel"
            )

        return redirect(
            "/accounts/dashboard/"
        )

    return render(
        request,
        "accounts/login.html"
    )


# ============================================================
# FORGOT PASSWORD
# ============================================================

def forgot_password(request):

    if request.method == "POST":

        email = request.POST.get(
            "email"
        )

        try:

            user = User.objects.get(
                email=email
            )

        except User.DoesNotExist:

            messages.error(
                request,
                "User not found"
            )

            return redirect(
                "forgot_password"
            )

        generate_otp(
            user.email,
            "reset"
        )

        return redirect(
            f"/accounts/reset-otp/{user.id}/"
        )

    return render(
        request,
        "accounts/forgot_password.html"
    )


# ============================================================
# RESET OTP
# ============================================================

def reset_otp(request, user_id):

    user = get_object_or_404(
        User,
        id=user_id
    )

    if request.method == "POST":

        code = request.POST.get(
            "otp",
            ""
        ).strip()

        otp = OTP.objects.filter(
            email=user.email,
            code=code,
            purpose="reset",
            is_used=False
        ).order_by(
            "-created_at"
        ).first()

        if otp and otp.is_valid():

            otp.is_used = True

            otp.save()

            request.session[
                "reset_user_id"
            ] = user.id

            return redirect(
                "set_new_password"
            )

        messages.error(
            request,
            "Invalid OTP"
        )

    return render(
        request,
        "accounts/reset_otp.html"
    )


# ============================================================
# SET NEW PASSWORD
# ============================================================

def set_new_password(request):

    user_id = request.session.get(
        "reset_user_id"
    )

    if not user_id:

        return redirect(
            "login"
        )

    user = get_object_or_404(
        User,
        id=user_id
    )

    if request.method == "POST":

        password = request.POST.get(
            "password"
        )

        confirm_password = request.POST.get(
            "confirm_password"
        )

        if password != confirm_password:

            messages.error(
                request,
                "Passwords do not match"
            )

            return redirect(
                "set_new_password"
            )

        user.set_password(
            password
        )

        user.save()

        request.session.pop(
            "reset_user_id",
            None
        )

        logout(
            request
        )

        messages.success(
            request,
            "Password reset successful"
        )

        return redirect(
            "login"
        )

    return render(
        request,
        "accounts/set_new_password.html"
    )


# ============================================================
# LOGOUT
# ============================================================

def logout_view(request):

    logout(
        request
    )

    return redirect(
        "/accounts/login/"
    )


# ============================================================
# PROFILE
# ============================================================

@login_required
def profile(
    request,
    username=None
):

    if username:

        user_obj = get_object_or_404(
            User,
            username=username
        )

    else:

        user_obj = request.user

    profile, _ = Profile.objects.get_or_create(
        user=user_obj
    )

    is_owner = (
        request.user == user_obj
    )

    orders = Order.objects.filter(
        buyer=user_obj
    ).select_related(
        "product"
    ).order_by(
        "-created_at"
    )

    return render(
        request,
        "accounts/profile.html",
        {
            "profile": profile,
            "user_obj": user_obj,
            "is_owner": is_owner,
            "orders": orders
        }
    )


# ============================================================
# PROFILE VIEW / UPDATE
# ============================================================

@login_required
def profile_view(request):

    profile, _ = Profile.objects.get_or_create(
        user=request.user
    )

    if request.method == "POST":

        request.user.username = request.POST.get(
            "username"
        )

        request.user.save()

        profile.bio = request.POST.get(
            "bio"
        )

        if "image" in request.FILES:

            profile.image = request.FILES[
                "image"
            ]

        profile.save()

        ActivityLog.objects.create(
            user=request.user,
            action="Profile Updated",
            description="User updated their profile."
        )

        return redirect(
            "profile_view"
        )

    return render(
        request,
        "accounts/profile.html",
        {
            "profile": profile,
            "is_owner": True,
            "user_obj": request.user
        }
    )


# ============================================================
# USER DASHBOARD
# ============================================================

@login_required
def dashboard(request):

    query = request.GET.get(
        "q"
    )

    products = Product.objects.select_related(
        "owner"
    ).all().order_by(
        "-id"
    )

    profiles = Profile.objects.all()

    if query:

        products = products.filter(
            title__icontains=query
        )

    from django.core.paginator import Paginator

    paginator = Paginator(
        products,
        12
    )

    page = request.GET.get(
        "page"
    )

    products = paginator.get_page(
        page
    )

    return render(
        request,
        "listings/index.html",
        {
            "products": products,
            "profiles": profiles
        }
    )

# ============================================================
# SELLER CONFIRM DELIVERY
# ============================================================

@login_required
@transaction.atomic
def seller_confirm_delivery(request, order_id):

    if request.method != "POST":

        return redirect(
            "listings:seller_orders"
        )

    # ========================================================
    # GET ORDER
    # ========================================================

    order = (
        Order.objects
        .select_for_update()
        .select_related(
            "product",
            "product__owner",
            "buyer"
        )
        .filter(
            id=order_id
        )
        .first()
    )

    if not order:

        messages.error(
            request,
            "Order not found."
        )

        return redirect(
            "listings:seller_orders"
        )

    # ========================================================
    # CHECK SELLER
    # ========================================================

    if order.product.owner != request.user:

        messages.error(
            request,
            "You are not allowed to confirm this delivery."
        )

        return redirect(
            "listings:seller_orders"
        )

    # ========================================================
    # CHECK ORDER STATUS
    # ========================================================

    if order.status == "cancelled":

        messages.error(
            request,
            "Cancelled orders cannot be confirmed."
        )

        return redirect(
            "listings:seller_orders"
        )

    if order.status == "delivered":

        messages.warning(
            request,
            "This order has already been completed."
        )

        return redirect(
            "listings:seller_orders"
        )

    # ========================================================
    # GET OR CREATE DELIVERY CONFIRMATION
    # ========================================================

    confirmation, created = (
        DeliveryConfirmation.objects
        .select_for_update()
        .get_or_create(
            order=order,
            defaults={
                "seller": request.user
            }
        )
    )

    # ========================================================
    # MAKE SURE SELLER IS CORRECT
    # ========================================================

    if confirmation.seller != request.user:

        messages.error(
            request,
            "You are not the seller of this order."
        )

        return redirect(
            "listings:seller_orders"
        )

    # ========================================================
    # PREVENT DUPLICATE CONFIRMATION
    # ========================================================

    if confirmation.seller_confirmed_at:

        messages.warning(
            request,
            "You have already confirmed this delivery."
        )

        return redirect(
            "listings:seller_orders"
        )

    # ========================================================
    # SELLER CONFIRMS DELIVERY
    # ========================================================

    confirmation.seller_confirmed_at = timezone.now()

    confirmation.save(
        update_fields=[
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
    # ADMIN NOTIFICATION
    # ========================================================

    admin_users = User.objects.filter(
        Q(is_admin=True) |
        Q(is_superuser=True)
    )

    for admin_user in admin_users:

        Notification.objects.create(
            user=admin_user,
            order=order,
            message=(
                f"Seller has confirmed delivery for "
                f"Order #{order.id}. "
                f"Admin confirmation is now required."
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
        .select_related(
            "buyer",
            "product",
            "product__owner",
            "delivery_confirmation"
        )
        .exclude(
            status="cancelled"
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