"""
Check `Plugin Writer's Guide`_ and `pulp_example`_ plugin
implementation for more details.

.. _Plugin Writer's Guide:
    http://docs.pulpproject.org/en/3.0/nightly/plugins/plugin-writer/index.html

.. _pulp_example:
    https://github.com/pulp/pulp_example/
"""

from pulpcore.plugin import viewsets as platform

from . import models, serializers


class PluginTemplateContentViewSet(platform.ContentViewSet):
    """
    A ViewSet for PluginTemplateContent.

    Define endpoint name which will appear in the API endpoint for this content type.
    For example::
        http://pulp.example.com/api/v3/content/plugin-template/

    Also specify queryset and serializer for PluginTemplateContent.
    """
    endpoint_name = 'plugin-template'
    queryset = models.PluginTemplateContent.objects.all()
    serializer_class = serializers.PluginTemplateContentSerializer


class PluginTemplateImporterViewSet(platform.ImporterViewSet):
    """
    A ViewSet for PluginTemplateImporter.

    Similar to the PluginTemplateContentViewSet above, define endpoint_name,
    queryset and serializer, at a minimum.
    """
    endpoint_name = 'plugin-template'
    queryset = models.PluginTemplateImporter.objects.all()
    serializer_class = serializers.PluginTemplateImporterSerializer


class PluginTemplatePublisherViewSet(platform.PublisherViewSet):
    """
    A ViewSet for PluginTemplatePublisher.

    Similar to the PluginTemplateContentViewSet above, define endpoint_name,
    queryset and serializer, at a minimum.
    """
    endpoint_name = 'plugin-template'
    queryset = models.PluginTemplatePublisher.objects.all()
    serializer_class = serializers.PluginTemplatePublisherSerializer
