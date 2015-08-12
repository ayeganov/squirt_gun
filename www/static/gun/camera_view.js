require([
    'dojo/dom',
    'stream/stream',
    'utils/imager',
    'dojo/domReady!'
],
function(dom, stream, imager)
{
    var camera_stream = new stream.Stream("camera");
    var image_viewer = new imager.Imager('view', 'fps_count', camera_stream);

    var shot_fired = dom.byId("shot_fired");
    var shoot_stream = new stream.Stream("shoot");

    shoot_stream.register(function(shot_type)
    {
        shot_fired.innerHTML = "Shot: " + shot_type;

        setTimeout(function() {
                shot_fired.innerHTML = "Shot: all clear";
            },
            500
        );
    });

    image_viewer.start();
});
