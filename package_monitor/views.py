import json

from django.http import JsonResponse
from django.shortcuts import render, redirect, reverse
from django.contrib.auth.decorators import login_required, permission_required

from . import __title__
from .app_settings import (
    PACKAGE_MONITOR_INCLUDE_PACKAGES,
    PACKAGE_MONITOR_SHOW_ALL_PACKAGES,
)
from .models import Distribution
from .tasks import update_distributions as task_update_distributions
from .utils import add_no_wrap_html, create_link_html, messages_plus, yesno_str

PACKAGE_LIST_FILTER_PARAM = "filter"


@login_required
@permission_required("package_monitor.basic_access")
def index(request):
    obj = Distribution.objects.first()
    updated_at = obj.updated_at if obj else None
    distributions_qs = Distribution.objects.currently_selected()
    context = {
        "app_title": __title__,
        "page_title": "Distribution packages",
        "updated_at": updated_at,
        "filter": request.GET.get(PACKAGE_LIST_FILTER_PARAM),
        "all_count": distributions_qs.count(),
        "current_count": distributions_qs.filter(is_outdated=False).count(),
        "outdated_count": distributions_qs.outdated_count(),
        "include_packages": PACKAGE_MONITOR_INCLUDE_PACKAGES,
        "show_all_packages": PACKAGE_MONITOR_SHOW_ALL_PACKAGES,
    }
    return render(request, "package_monitor/index.html", context)


@login_required
@permission_required("package_monitor.basic_access")
def package_list_data(request) -> JsonResponse:
    """Returns the packages as list in JSON.
    Specify different subsets with the "filter" GET parameter
    """
    my_filter = request.GET.get(PACKAGE_LIST_FILTER_PARAM, "")
    distributions_qs = Distribution.objects.currently_selected()

    if my_filter == "outdated":
        distributions_qs = distributions_qs.filter(is_outdated=True)
    elif my_filter == "current":
        distributions_qs = distributions_qs.filter(is_outdated=False)

    data = list()
    for dist in distributions_qs.order_by("name"):
        name_link_html = (
            create_link_html(dist.website_url, dist.name)
            if dist.website_url
            else dist.name
        )
        if dist.is_outdated:
            name_link_html += '&nbsp;<i class="fas fa-exclamation-circle" title="Update available"></i>'

        if dist.apps:
            _lst = [add_no_wrap_html(row) for row in json.loads(dist.apps)]
            apps_html = "<br>".join(_lst) if _lst else "-"
        else:
            apps_html = ""

        if dist.used_by:
            used_by_html = "<br>".join(
                [
                    add_no_wrap_html(
                        create_link_html(row["homepage_url"], row["name"])
                        if row["homepage_url"]
                        else row["name"]
                    )
                    for row in json.loads(dist.used_by)
                ]
            )
        else:
            used_by_html = ""

        data.append(
            {
                "name_link": add_no_wrap_html(name_link_html),
                "apps": apps_html,
                "used_by": used_by_html,
                "current": dist.installed_version,
                "latest": dist.latest_version if dist.latest_version else "-",
                "is_outdated": dist.is_outdated,
                "is_outdated_str": yesno_str(dist.is_outdated),
                "description": dist.description,
            }
        )

    return JsonResponse(data, safe=False)


@login_required
@permission_required("package_monitor.basic_access")
def update_distributions(request):
    task_update_distributions.delay()
    messages_plus.success(
        request,
        message=(
            "Data update as been started. "
            "Reload this page in about 1 - 2 minutes for the results."
        ),
    )
    return redirect(reverse("package_monitor:index"))
