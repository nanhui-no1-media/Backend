from django.contrib import admin

from .models import Proposal, Vote


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = ["title", "proposal_type", "status", "creator", "created_at"]
    list_filter = ["proposal_type", "status"]
    search_fields = ["title", "description"]
    readonly_fields = ["created_at", "updated_at", "reviewed_at", "approved_at", "voting_end_at"]


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ["proposal", "voter", "vote_choice", "created_at"]
    list_filter = ["vote_choice"]
