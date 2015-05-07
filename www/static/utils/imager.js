define([
    "dojo/dom",
    "dojo/dom-attr",
    "utils/fps_count",
    "utils/common",
    "dojo/domReady!"
],
function(dom, dom_attr, fps_count, common)
{
    /**
     * This class is responsible for drawing images coming across the websocket
     * stream onto the provided canvas. It is assumed the canvas will be
     * properly sized to fit the images. The websocket stream must provide
     * URL's to images, not actual image data. Imager will also count number of
     * frames per second and will display that count in the provided field with
     * id of "fps_id".
     *
     * @param canvas_id - id of the canvas to draw images on
     * @param fps_id - id of the html element to contain fps count
     * @param stream - websocket stream providing the URL's to images
     */
    function Imager(canvas_id, fps_id, stream)
    {
        var self = this;

        var init = function()
        {
            self._canvas = dom.byId(canvas_id);
            self._ctx = self._canvas.getContext('2d');
            self._fps_node = dom.byId(fps_id);
            self._stream = stream;
            self._fps_counter = new fps_count.FPSCounter();
            self._image = new Image();
            self._loading = false;
            self._image.onload = self._image_load;
        };

        self.start = function()
        {
            self._stream.register(self._draw_image);
        };

        self.stop = function()
        {
            self._stream.unregister(self._draw_image);
            self._clear_screen();
        };

        self._clear_screen = function()
        {
            // setting new width, or height value on canvas clears it.
            self._canvas.width = self._canvas.width;
        };

        self._image_load = function()
        {
            self._ctx.drawImage(self._image, 0, 0);
            self._fps_counter.count_frame();
            dom_attr.set(self._fps_node, 'innerHTML', 'FPS: ' + self._fps_counter.get_fps());
            self._loading = false;
        };

        self._draw_image = function(img_url)
        {
            var full_url = common.WEB_ADDRESS + img_url;
            if(self._loading)
            {
                console.log("Skipping " + img_url);
            }
            else
            {
                self._loading = true;
                self._image.src = img_url;
            }
        };

        init();
    };

    return {
        Imager: Imager
    };
});
