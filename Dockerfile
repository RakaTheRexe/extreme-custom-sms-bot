# Python 3.10 এর হালকা ভার্সন ব্যবহার করছি
FROM python:3.10-slim

# কাজের ফোল্ডার সেট করা
WORKDIR /app

# টাইমজোন সেট করা (বাংলাদেশ সময়)
# এটা না দিলে সার্ভারের সময় UTC তে থাকবে এবং বোনাস রিসেট হতে সমস্যা হবে
ENV TZ=Asia/Dhaka
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# লাইব্রেরি ইন্সটল করা
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# আপনার মেইন কোড কপি করা
COPY bot.py .

# বট চালু করার কমান্ড
CMD ["python", "bot.py"]
