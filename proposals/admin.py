from django.contrib import admin

from .models import Proposal, ProposalAttachment, Vote


class ProposalAttachmentInline(admin.TabularInline):
    model = ProposalAttachment
    extra = 0
    readonly_fields = ["uploaded_by", "file_type", "file_name", "file_size", "uploaded_at"]


@admin.register(Proposal)
class ProposalAdmin(admin.ModelAdmin):
    list_display = ["title", "proposal_type", "status", "creator", "created_at"]
    list_filter = ["proposal_type", "status"]
    search_fields = ["title", "description"]
    readonly_fields = ["created_at", "updated_at", "reviewed_at", "approved_at", "voting_end_at"]
    inlines = [ProposalAttachmentInline]


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ["proposal", "voter", "vote_choice", "created_at"]
    list_filter = ["vote_choice"]


@admin.register(ProposalAttachment)
class ProposalAttachmentAdmin(admin.ModelAdmin):
    list_display = ["file_name", "proposal", "uploaded_by", "file_type", "file_size", "uploaded_at"]
    list_filter = ["file_type"]
