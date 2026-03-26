from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse


@login_required
def accessrule_list(request):
    return render(request, "GateCore/accessrule_list.html", {
        "accessrule_api_url": "/api/gatecore/accessrules/",
        "accessrule_create_url": reverse("gatecore_accessrule_create"),
    })


@login_required
def accessrule_create(request):
    return render(request, "GateCore/accessrule_form.html", {
        "mode": "create",
        "accessrule_api_url": "/api/gatecore/accessrules/",
        "accessrule_list_url": reverse("gatecore_accessrule_list"),
    })


@login_required
def accessrule_update(request, pk):
    return render(request, "GateCore/accessrule_form.html", {
        "mode": "edit",
        "rule_id": pk,
        "accessrule_detail_api_url": f"/api/gatecore/accessrules/{pk}/",
        "accessrule_api_url": f"/api/gatecore/accessrules/{pk}/",
        "accessrule_list_url": reverse("gatecore_accessrule_list"),
    })


@login_required
def accessrule_delete(request, pk):
    return render(request, "GateCore/accessrule_confirm_delete.html", {
        "rule_id": pk,
        "accessrule_detail_api_url": f"/api/gatecore/accessrules/{pk}/",
        "accessrule_api_url": f"/api/gatecore/accessrules/{pk}/",
        "accessrule_list_url": reverse("gatecore_accessrule_list"),
    })
