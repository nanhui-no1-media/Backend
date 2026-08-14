from django.contrib import admin

from .models import Activity, Ballot, BallotSelection, Submission, VoteOption


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ["title", "type", "status", "creator", "end_at", "created_at"]
    list_filter = ["type", "status"]
    search_fields = ["title", "body"]
    date_hierarchy = "created_at"


@admin.register(VoteOption)
class VoteOptionAdmin(admin.ModelAdmin):
    list_display = ["text", "activity", "order", "created_at"]
    list_filter = ["activity__type"]
    search_fields = ["text"]
    autocomplete_fields = ["activity"]


@admin.register(Ballot)
class BallotAdmin(admin.ModelAdmin):
    list_display = ["activity", "voter", "created_at"]
    list_filter = ["activity__type"]
    search_fields = ["activity__title", "voter__username"]
    autocomplete_fields = ["activity", "voter"]


@admin.register(BallotSelection)
class BallotSelectionAdmin(admin.ModelAdmin):
    list_display = ["ballot", "option", "created_at"]
    search_fields = ["option__text"]
    autocomplete_fields = ["ballot", "option"]


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ["activity", "submitter", "review_status", "reviewed_at", "created_at"]
    list_filter = ["review_status", "activity__type"]
    search_fields = ["activity__title", "submitter__username", "review_comment"]
    autocomplete_fields = ["activity", "submitter", "reviewed_by"]
