tools = [
    {
        "type": "function",
        "function": {
            "name": "get_all_banks_and_rates_for_chat_bot",
            "description": "Tra cứu, so sánh lãi suất ngân hàng hoặc tìm lãi suất cao nhất.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": ["string", "null"], "description": "Tên ngân hàng hoặc null."},
                    "type": {"type": ["string", "null"], "description": "STATE, PRIVATE hoặc null."},
                    "code": {"type": ["string", "null"], "description": "Mã ngân hàng hoặc null."}
                },
                "required": ["name", "type", "code"],
                "additionalProperties": False
            },
            "strict": True,
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_deposit_interest",
            "description": "Tính lãi tiền gửi theo ngân hàng, số tiền, kỳ hạn, kênh và ngày gửi.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bank_id": {"type": ["integer", "null"], "description": "ID ngân hàng hoặc null."},
                    "bank_code": {"type": ["string", "null"], "description": "Mã ngân hàng hoặc null."},
                    "bank_name": {"type": ["string", "null"], "description": "Tên ngân hàng hoặc null."},
                    "channel": {"type": ["string", "null"], "description": "ONLINE hoặc COUNTER."},
                    "term_month": {"type": "integer", "description": "Kỳ hạn tháng."},
                    "amount": {"type": "number", "description": "Số tiền VND."},
                    "deposit_date": {"type": ["string", "null"], "description": "YYYY-MM-DD hoặc null."}
                },
                "required": [
                    "bank_id",
                    "bank_code",
                    "bank_name",
                    "channel",
                    "term_month",
                    "amount",
                    "deposit_date"
                ],
                "additionalProperties": False
            },
            "strict": True,
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_saving_plan",
            "description": "Lập hoặc tối ưu kế hoạch gửi tiết kiệm theo mục tiêu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": ["integer", "null"], "description": "ID user hoặc null."},
                    "name": {"type": ["string", "null"], "description": "Tên kế hoạch hoặc null."},
                    "duration_month": {"type": "integer", "description": "Thời gian tháng."},
                    "total_amount": {"type": "number", "description": "Số tiền ban đầu."},
                    "goal_amount": {"type": ["number", "null"], "description": "Mục tiêu cuối kỳ hoặc null."},
                    "monthly_extra": {"type": ["number", "null"], "description": "Gửi thêm mỗi tháng."},
                    "extra_schedule": {
                        "type": ["array", "null"],
                        "description": "Lịch gửi thêm.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "month": {"type": "integer"},
                                "amount": {"type": "number"}
                            },
                            "required": ["month", "amount"],
                            "additionalProperties": False
                        }
                    },
                    "withdrawal_schedule": {
                        "type": ["array", "null"],
                        "description": "Lịch rút tiền.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "month": {"type": "integer"},
                                "amount": {"type": "number"}
                            },
                            "required": ["month", "amount"],
                            "additionalProperties": False
                        }
                    },
                    "prefer_rate": {"type": ["string", "null"], "description": "ONLINE hoặc COUNTER."},
                    "risk_tolerance": {"type": ["string", "null"], "description": "low, medium, high."},
                    "algorithm_used": {"type": ["string", "null"], "description": "auto, dp, greedy, monte_carlo, rule_based."},
                    "codes": {
                        "type": ["array", "null"],
                        "description": "Mã ngân hàng hoặc null.",
                        "items": {"type": "string"}
                    },
                    "notes": {"type": ["string", "null"], "description": "Ghi chú hoặc null."}
                },
                "required": [
                    "user_id",
                    "name",
                    "duration_month",
                    "total_amount",
                    "goal_amount",
                    "monthly_extra",
                    "extra_schedule",
                    "withdrawal_schedule",
                    "prefer_rate",
                    "risk_tolerance",
                    "algorithm_used",
                    "codes",
                    "notes"
                ],
                "additionalProperties": False
            },
            "strict": True,
        }
    }
]
