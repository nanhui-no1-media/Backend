from reviews.models import Review


def approve_news(news):
    """测试辅助：给已有新闻补一条「通过」审核，使其公开可见。"""
    Review.objects.update_or_create(
        news=news,
        defaults={"status": Review.STATUS_APPROVED},
    )
    return news
