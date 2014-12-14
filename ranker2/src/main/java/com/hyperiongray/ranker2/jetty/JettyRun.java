package com.hyperiongray.ranker2.jetty;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.ServletException;
import java.io.IOException;
import java.text.DecimalFormat;

import org.apache.lucene.analysis.Analyzer;
import org.apache.lucene.analysis.core.SimpleAnalyzer;
import org.apache.lucene.index.memory.MemoryIndex;
import org.apache.lucene.queryparser.classic.QueryParser;
import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.server.Request;
import org.eclipse.jetty.server.handler.AbstractHandler;

/**
 * Created by mark on 12/14/14.
 */
public class JettyRun extends AbstractHandler {
    private static DecimalFormat df = new DecimalFormat("0.00");

    public void handle(String target,
                       Request baseRequest,
                       HttpServletRequest request,
                       HttpServletResponse response)
            throws IOException, ServletException {
        String html = request.getParameter("html");
        String keyPhrase = request.getParameter("keyPhrase");

        response.setContentType("text/html;charset=utf-8");
        response.setStatus(HttpServletResponse.SC_OK);
        baseRequest.setHandled(true);

        if (html != null && keyPhrase != null && !html.trim().isEmpty()  && !keyPhrase.trim().isEmpty()) {
            // TODO do ranking
            String ranking = getRank(html, keyPhrase);
            response.getWriter().println(ranking);
        } else {
            response.getWriter().println("<h1>Ranker2 - please give me some work to do</h1>");
        }
    }

    public static void main(String[] args) throws Exception {
        Server server = new Server(8080);
        server.setHandler(new JettyRun());

        server.start();
        server.join();
    }
    private String getRank(String html, String keyPhrase) {
        String rank = "";
        try {
            //Analyzer analyzer = PatternAnalyzer.DEFAULT_ANALYZER;
            Analyzer analyzer = new SimpleAnalyzer();
            MemoryIndex index = new MemoryIndex();
            index.addField("content", html, analyzer);
            QueryParser parser = new QueryParser("content", analyzer);
            double score = index.search(parser.parse(keyPhrase));
            rank = df.format(score);
        } catch (Exception e) {
            e.printStackTrace();
        }
        return rank;
    }
}
