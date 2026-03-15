from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_admin_order_keyboard(order_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅ Order Granted", callback_data=f"approve_order|{order_id}"),
            InlineKeyboardButton("❌ Deny Order", callback_data=f"deny_order|{order_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_apply_job_keyboard(bot_username: str, order_id: str) -> InlineKeyboardMarkup:
    url = f"https://t.me/{bot_username}?start=apply_{order_id}"
    keyboard = [
        [InlineKeyboardButton("📝 APPLY FOR THIS ORDER", url=url)]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_client_selection_keyboard(order_id: str, editor_id: str, portfolio_link: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔗 View Portfolio", url=portfolio_link)],
        [InlineKeyboardButton("⭐ Select Editor", callback_data=f"select_editor|{order_id}|{editor_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_grant_assignment_keyboard(order_id: str, editor_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(f"🔒 Assign Editor", callback_data=f"grant_assignment|{order_id}|{editor_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_client_review_keyboard(order_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"rate|{order_id}|5"),
            InlineKeyboardButton("⭐⭐⭐⭐", callback_data=f"rate|{order_id}|4")
        ],
        [
            InlineKeyboardButton("⭐⭐⭐", callback_data=f"rate|{order_id}|3"),
            InlineKeyboardButton("⭐⭐", callback_data=f"rate|{order_id}|2"),
            InlineKeyboardButton("⭐", callback_data=f"rate|{order_id}|1")
        ],
        [InlineKeyboardButton("🔄 Need Revision", callback_data=f"req_revision|{order_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_revision_keyboard(order_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🔄 Yes, need revision", callback_data=f"req_revision|{order_id}"),
            InlineKeyboardButton("✅ No, approve final", callback_data=f"approve_final|{order_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_payment_collection_keyboard(order_id: str, editor_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("💰 Collected", callback_data=f"payment_action|collected|{order_id}|{editor_id}"),
            InlineKeyboardButton("⏳ Not Yet Collected", callback_data=f"payment_action|notyet|{order_id}|{editor_id}"),
            InlineKeyboardButton("❌ Cancel Order", callback_data=f"payment_action|cancel|{order_id}|{editor_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_order_category_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📱 Instagram Reel", callback_data="category|Instagram Reel")],
        [InlineKeyboardButton("▶️ YouTube Video", callback_data="category|YouTube Video")],
        [InlineKeyboardButton("🎬 Short Film / Ad", callback_data="category|Short Film")],
        [InlineKeyboardButton("✍️ Other (Type below)", callback_data="category|Other")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_order_duration_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("⏱️ < 30 sec", callback_data="duration|< 30 sec")],
        [InlineKeyboardButton("⏱️ 30 - 60 sec", callback_data="duration|30 - 60 sec")],
        [InlineKeyboardButton("⏱️ 1 - 5 mins", callback_data="duration|1 - 5 mins")],
        [InlineKeyboardButton("⏱️ > 5 mins", callback_data="duration|> 5 mins")],
        [InlineKeyboardButton("✍️ Other (Type below)", callback_data="duration|Other")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_order_videos_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("1 Video", callback_data="videos|1")],
        [InlineKeyboardButton("2-5 Videos", callback_data="videos|2-5")],
        [InlineKeyboardButton("5+ Videos", callback_data="videos|5+")],
        [InlineKeyboardButton("✍️ Other (Type below)", callback_data="videos|Other")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_order_deadline_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("⏰ 24 Hours", callback_data="deadline|24 Hours")],
        [InlineKeyboardButton("📅 2 Days", callback_data="deadline|2 Days")],
        [InlineKeyboardButton("📅 1 Week", callback_data="deadline|1 Week")],
        [InlineKeyboardButton("✍️ Other (Type below)", callback_data="deadline|Other")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_payment_collection_keyboard(order_id: str, editor_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("💰 Collected (Start Editor)", callback_data=f"payment_action|collected|{order_id}|{editor_id}")],
        [InlineKeyboardButton("⏳ Not Yet (Wait)", callback_data=f"payment_action|not_yet|{order_id}|{editor_id}")],
        [InlineKeyboardButton("❌ Canceled", callback_data=f"payment_action|canceled|{order_id}|{editor_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📢 Post a Project", callback_data="admin_post_start")],
        [InlineKeyboardButton("🆕 Pending Orders", callback_data="dashboard|pending_orders")],
        [InlineKeyboardButton("📥 Editor Applications", callback_data="dashboard|applications")],
        [InlineKeyboardButton("📊 View Revenue & Payouts", callback_data="dashboard|revenue")],
        [InlineKeyboardButton("📋 View Order Statuses", callback_data="dashboard|status")],
        [InlineKeyboardButton("👥 View Active Assignments", callback_data="dashboard|assignments")],
        [InlineKeyboardButton("🔄 Refresh Dashboard", callback_data="dashboard|refresh")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_editor_skills_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("✂️ Video Editing", callback_data="skill|Video Editing")],
        [InlineKeyboardButton("🎨 Motion Graphics", callback_data="skill|Motion Graphics")],
        [InlineKeyboardButton("🌈 Color Grading", callback_data="skill|Color Grading")],
        [InlineKeyboardButton("🖼️ Thumbnails", callback_data="skill|Thumbnails")]
    ]
    return InlineKeyboardMarkup(keyboard)
