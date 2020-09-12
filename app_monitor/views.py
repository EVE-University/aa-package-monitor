import json

from django.http import JsonResponse
from django.shortcuts import render, redirect, reverse
from django.contrib.auth.decorators import login_required, permission_required

from . import __title__
from .models import Distribution
from .tasks import update_distributions as task_update_distributions
from .utils import create_link_html, yesno_str, messages_plus


@login_required
@permission_required("app_monitor.basic_access")
def index(request):
    obj = Distribution.objects.first()
    updated_at = obj.updated_at if obj else None
    outdated_count = Distribution.objects.filter(is_outdated=True).count()
    if outdated_count > 0:
        messages_plus.warning(
            request,
            message=(
                f"{outdated_count} distribution packages are outdated "
                "and should be updated."
            ),
        )
    context = {"app_title": __title__, "updated_at": updated_at}
    return render(request, "app_monitor/index.html", context)


@login_required
@permission_required("app_monitor.basic_access")
def app_list_data(request):
    data = list()
    for dist in Distribution.objects.order_by("name"):
        name_link_html = (
            create_link_html(dist.website_url, dist.name)
            if dist.website_url
            else dist.name
        )
        if dist.is_outdated:
            name_link_html += '&nbsp;<i class="fas fa-exclamation-circle"></i>'

        data.append(
            {
                "name_link": name_link_html,
                "apps": "<br>".join(json.loads(dist.apps)),
                "current": dist.installed_version,
                "latest": dist.latest_version if dist.latest_version else "-",
                "is_outdated": dist.is_outdated,
                "is_outdated_str": yesno_str(dist.is_outdated),
                "description": dist.description,
            }
        )

    return JsonResponse(data, safe=False)


@login_required
@permission_required("app_monitor.basic_access")
def update_distributions(request):
    task_update_distributions.delay()
    messages_plus.success(
        request,
        message=(
            "Data update as been started. "
            "Reload this page in about 30 seconds for the results."
        ),
    )
    return redirect(reverse("app_monitor:index"))
