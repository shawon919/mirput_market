from django.urls import path

from . import views


urlpatterns = [

    # ========================================================
    # AUTH
    # ========================================================

    path(
        "register/",
        views.register,
        name="register"
    ),

    path(
        "login/",
        views.login_view,
        name="login"
    ),

    path(
        "logout/",
        views.logout_view,
        name="logout"
    ),

    path(
        "verify/<int:user_id>/",
        views.verify_otp,
        name="verify_otp"
    ),

    path(
        "resend-otp/<int:user_id>/",
        views.resend_otp,
        name="resend_otp"
    ),


    # ========================================================
    # PASSWORD RESET
    # ========================================================

    path(
        "forgot-password/",
        views.forgot_password,
        name="forgot_password"
    ),

    path(
        "reset-otp/<int:user_id>/",
        views.reset_otp,
        name="reset_otp"
    ),

    path(
        "set-new-password/",
        views.set_new_password,
        name="set_new_password"
    ),


    # ========================================================
    # USER
    # ========================================================

    path(
        "dashboard/",
        views.dashboard,
        name="dashboard"
    ),

    # Current logged-in user's profile

    path(
        "profile/",
        views.profile_view,
        name="profile_view"
    ),

    # Specific user's profile

    path(
        "profile/<str:username>/",
        views.profile,
        name="profile"
    ),


    # ========================================================
    # ADMIN
    # ========================================================

    path(
        "adminpanel/",
        views.adminpanel,
        name="adminpanel"
    ),

    path(
        "adminpanel/users/",
        views.admin_users,
        name="admin_users"
    ),

    path(
        "adminpanel/users/<int:user_id>/",
        views.admin_user_detail,
        name="admin_user_detail"
    ),

    path(
        "adminpanel/sales/",
        views.admin_sales,
        name="admin_sales"
    ),

    path(
        "adminpanel/deliveries/",
        views.admin_delivery_confirmations,
        name="admin_delivery_confirmations"
    ),

    path(
        "adminpanel/revenue/",
        views.admin_revenue,
        name="admin_revenue"
    ),

    path(
        "adminpanel/order/<int:order_id>/complete/",
        views.complete_delivery,
        name="complete_delivery"
    ),
    
    path(
    "seller/orders/",
    views.seller_orders,
    name="seller_orders"
),

path(
    "seller/order/<int:order_id>/confirm-delivery/",
    views.seller_confirm_delivery,
    name="seller_confirm_delivery"
),
]