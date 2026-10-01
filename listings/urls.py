from django.urls import path
from . import views

app_name = 'listings'

urlpatterns = [

    path(
        "dashboard/",
        views.dashboard,
        name="dashboard"
    ),

    path(
        "add/",
        views.add_product,
        name="add_product"
    ),

    path(
        "product/<int:pk>/",
        views.product_detail,
        name="product_detail"
    ),

    path(
        "delete/<int:pk>/",
        views.delete_product,
        name="delete_product"
    ),

    path(
        "buy/<int:pk>/",
        views.buy_product,
        name="buy_product"
    ),

    path(
        "cart/",
        views.cart_view,
        name="cart"
    ),

    path(
        "cart/add/<int:pk>/",
        views.add_to_cart,
        name="add_to_cart"
    ),

    path(
        "cart/remove/<int:pk>/",
        views.remove_from_cart,
        name="remove_from_cart"
    ),

    path(
        "cart/place-order/",
        views.place_order_cart,
        name="place_order_cart"
    ),

    path(
        "cart/update/<int:pk>/<str:action>/",
        views.update_cart,
        name="update_cart"
    ),

    path(
        "order/<int:pk>/",
        views.order_detail,
        name="order_detail"
    ),

    path(
        "my-orders/",
        views.my_orders,
        name="my_orders"
    ),

    path(
        "order/cancel/<int:pk>/",
        views.cancel_order,
        name="cancel_order"
    ),

    path(
        "notifications/",
        views.notifications_view,
        name="notifications"
    ),

    path(
        "notifications/read/<int:pk>/",
        views.mark_notification_read,
        name="mark_notification_read"
    ),

    path(
        "notifications/open/<int:pk>/",
        views.open_notification,
        name="open_notification"
    ),

    path(
        "order/confirm/<int:pk>/",
        views.confirm_order,
        name="confirm_order"
    ),

    path(
        "user_profile/<int:id>/",
        views.userProfileView,
        name="user_profile"
    ),

    path(
        "messages/<int:id>/",
        views.userMessage,
        name="messages"
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