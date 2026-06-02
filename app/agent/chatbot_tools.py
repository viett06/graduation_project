number_like = ["number", "integer", "string", "null"]
integer_like = ["integer", "string", "null"]

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_rates",
            "description": (
                "Tra cứu lãi suất tiết kiệm từ backend. Dùng khi người dùng hỏi lãi suất, "
                "lãi suất cao nhất, danh sách lãi suất, hoặc so sánh lãi suất giữa các ngân hàng. "
                "Không dùng để tính số tiền lãi thực nhận."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bank_name": {
                        "type": ["string", "null"],
                        "description": "Tên một ngân hàng người dùng nhắc tới, ví dụ Vietcombank."
                    },
                    "bank_names": {
                        "type": ["array", "string", "null"],
                        "description": "Danh sách tên ngân hàng nếu người dùng nhắc nhiều ngân hàng.",
                        "items": {"type": "string"}
                    },
                    "bank_code": {
                        "type": ["string", "null"],
                        "description": "Mã một ngân hàng người dùng nhắc tới, ví dụ VCB, BIDV, PVB."
                    },
                    "bank_codes": {
                        "type": ["array", "string", "null"],
                        "description": "Danh sách mã ngân hàng nếu người dùng nhắc nhiều mã.",
                        "items": {"type": "string"}
                    },
                    "bank_type": {
                        "type": ["string", "null"],
                        "description": "Loại ngân hàng nếu có, ví dụ STATE hoặc PRIVATE."
                    },
                    "term_month": {
                        "type": integer_like,
                        "description": "Kỳ hạn gửi theo tháng, ví dụ 6 hoặc '6'."
                    },
                    "channel": {
                        "type": ["string", "null"],
                        "description": "Kênh gửi nếu có: ONLINE hoặc COUNTER."
                    },
                    "amount": {
                        "type": number_like,
                        "description": "Số tiền gửi nếu người dùng nêu, ví dụ 500000000 hoặc '500 triệu'."
                    },
                    "sort": {
                        "type": ["string", "null"],
                        "enum": ["highest", "compare", "list", None],
                        "description": "highest nếu hỏi cao nhất/tốt nhất, compare nếu so sánh, list nếu liệt kê."
                    },
                    "limit": {
                        "type": integer_like,
                        "description": "Số dòng tối đa cần lấy, ví dụ 5 hoặc '5'."
                    }
                },
                "additionalProperties": False
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_deposit_interest",
            "description": (
                "Tính số tiền lãi và tổng tiền cuối kỳ khi gửi tiết kiệm ở một ngân hàng. "
                "Model chỉ cung cấp mã hoặc tên ngân hàng, backend sẽ tự resolve bank_id nội bộ."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bank_code": {
                        "type": ["string", "null"],
                        "description": "Mã ngân hàng nếu người dùng nêu, ví dụ VCB, BIDV, PVB."
                    },
                    "bank_name": {
                        "type": ["string", "null"],
                        "description": "Tên ngân hàng nếu người dùng nêu."
                    },
                    "channel": {
                        "type": ["string", "null"],
                        "description": "Kênh gửi nếu có: ONLINE hoặc COUNTER."
                    },
                    "term_month": {
                        "type": integer_like,
                        "description": "Kỳ hạn gửi theo tháng, ví dụ 6 hoặc '6'."
                    },
                    "amount": {
                        "type": number_like,
                        "description": "Số tiền gửi VND, ví dụ 500000000 hoặc '500 triệu'."
                    },
                    "deposit_date": {
                        "type": ["string", "null"],
                        "description": "Ngày gửi dạng YYYY-MM-DD nếu người dùng nêu."
                    }
                },
                "additionalProperties": False
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_bank_interest",
            "description": (
                "So sánh tiền lãi hoặc tổng tiền nhận được giữa ít nhất hai ngân hàng. "
                "Nếu thiếu số tiền hoặc kỳ hạn, backend sẽ trả missing_fields để hỏi người dùng bổ sung."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "bank_codes": {
                        "type": ["array", "string", "null"],
                        "description": "Danh sách mã ngân hàng, ví dụ ['PVB', 'SGB'].",
                        "items": {"type": "string"}
                    },
                    "bank_names": {
                        "type": ["array", "string", "null"],
                        "description": "Danh sách tên ngân hàng nếu người dùng không nêu mã.",
                        "items": {"type": "string"}
                    },
                    "channel": {
                        "type": ["string", "null"],
                        "description": "Kênh gửi nếu có: ONLINE hoặc COUNTER."
                    },
                    "term_month": {
                        "type": integer_like,
                        "description": "Kỳ hạn gửi theo tháng, ví dụ 6 hoặc '6'."
                    },
                    "amount": {
                        "type": number_like,
                        "description": "Số tiền gửi VND, ví dụ 500000000 hoặc '500 triệu'."
                    },
                    "deposit_date": {
                        "type": ["string", "null"],
                        "description": "Ngày gửi dạng YYYY-MM-DD nếu người dùng nêu."
                    }
                },
                "additionalProperties": False
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_saving_plan",
            "description": (
                "Lập hoặc tối ưu kế hoạch gửi tiết kiệm theo mục tiêu. "
                "Nếu thiếu tổng tiền hoặc thời gian, backend sẽ trả missing_fields."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": ["string", "null"],
                        "description": "Tên kế hoạch nếu người dùng nêu."
                    },
                    "duration_month": {
                        "type": integer_like,
                        "description": "Thời gian kế hoạch theo tháng, ví dụ 12 hoặc '12'."
                    },
                    "total_amount": {
                        "type": number_like,
                        "description": "Số tiền ban đầu, ví dụ 100000000 hoặc '100 triệu'."
                    },
                    "goal_amount": {
                        "type": number_like,
                        "description": "Mục tiêu cuối kỳ nếu có."
                    },
                    "prefer_rate": {
                        "type": ["string", "null"],
                        "description": "ONLINE hoặc COUNTER."
                    },
                    "bank_codes": {
                        "type": ["array", "string", "null"],
                        "description": "Mã ngân hàng muốn ưu tiên nếu có.",
                        "items": {"type": "string"}
                    },
                    "notes": {
                        "type": ["string", "null"],
                        "description": "Ghi chú nếu có."
                    }
                },
                "additionalProperties": False
            },
        }
    }
]
